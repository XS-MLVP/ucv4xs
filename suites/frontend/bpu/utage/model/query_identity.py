"""Logical alias ownership, not a physical-address coverage matrix."""
from dataclasses import dataclass
from suites.frontend.bpu.utage.model.semantic import Context,indices,tag
from suites.frontend.bpu.utage.case.definitions import SHADOW_CAPACITY

PC,POSITION=0x40000000,5
READ_PCS=(PC,PC+0x100)
MODES=('serial','adjacent')
RULES=('same-match-distinct-complete-read-identities','opposed-normally-learned-prestate',
    'adjacent-overlapping-originals','target-three-actual-read-ages','other-originals-preserved',
    'complete-fresh-feedbacks-once','mixed-owner-version-turnover','actual-feedback-cadence',
    'fresh-both-identity-consumers','all-protection-preserved','completed-originals-immutable')


@dataclass(frozen=True)
class Program:
    teacher:int
    mode:str

    def __post_init__(self):
        if type(self.teacher) is not int or self.teacher not in (0,1) or self.mode not in MODES:
            raise ValueError('one original learning owner and an existing feedback cadence required')

    @property
    def label(self):return ('taken-first' if self.teacher==0 else 'not-taken-first')+'.'+self.mode
    @property
    def cohort_owners(self):return (1-self.teacher,self.teacher)*3+(1-self.teacher,)
    @property
    def turnover_owners(self):return tuple(i%2 for i in range(SHADOW_CAPACITY))

    @staticmethod
    def read_indices(owner):return indices(READ_PCS[owner],Context())
    @staticmethod
    def actual(owner):return 1-owner
    @staticmethod
    def initial(owner):return 4 if owner==0 else 3
    @staticmethod
    def step(owner):return 1 if owner==0 else -1

    def counter(self,owner,subsequent=0):
        if owner not in (0,1) or type(subsequent) is not int or not 0<=subsequent<=SHADOW_CAPACITY:
            raise ValueError('declared identity and bounded chronological learning count required')
        updates=int(owner==self.teacher)+self.turnover_owners[:subsequent].count(owner)
        return max(0,min(7,self.initial(owner)+self.step(owner)*updates))

    def expected(self,owner,*,relation=None,subsequent=0):
        counter=self.initial(owner) if relation in ('before','same-boundary') else self.counter(owner,subsequent)
        return 1,0,counter,self.actual(owner)

    def protection(self,phase):
        values=[0]*1024
        if phase=='reset':return tuple(values)
        if phase not in ('prepared','first-effect','turnover'):raise ValueError('declared protection epoch required')
        for owner in (0,1):
            values[self.read_indices(owner)[0]]=3 if phase=='turnover' else 1+int(phase=='first-effect' and owner==self.teacher)
        return tuple(values)

    def versions(self):
        counters=[None,None];protection=[0,0];result=[]
        for owner in (0,1,self.teacher,*self.turnover_owners):
            previous=counters[owner]
            counters[owner]=self.initial(owner) if previous is None else max(0,min(7,previous+self.step(owner)))
            old=protection[owner]
            protection[owner]=1 if previous is None else min(3,old+1)
            index=self.read_indices(owner)[0]
            changes=() if protection[owner]==old else ((index,old,protection[owner]),)
            result.append(dict(owner=owner,protection_changes=changes,cell=dict(valid=1,data_valid=1,index=index,
                tag=tag(PC,Context(),0),position=POSITION,counter=counters[owner])))
        return result

    def state(self):
        return dict(teacher=self.teacher,mode=self.mode,match_pc=PC,match_history=0,read_pcs=READ_PCS,
            complete_indices=tuple(self.read_indices(owner) for owner in (0,1)),
            initial_counters=tuple(self.initial(owner) for owner in (0,1)),cohort_owners=self.cohort_owners,
            turnover_owners=self.turnover_owners,physical_enumeration=False,full_FTQ_reachability_claimed=False)
