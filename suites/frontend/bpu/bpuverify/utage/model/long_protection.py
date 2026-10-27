"""Logical provider promotion and independently owned long-history learning."""
from dataclasses import dataclass
from bpuverify.utage.model.semantic import Context,tag
from bpuverify.utage.model.usefulness_events import ProtectionState
from bpuverify.utage.model.query_identity import PC,POSITION,READ_PCS as ORIGINAL_READ_PCS,MODES,SHADOW_CAPACITY

READ_PCS=(*ORIGINAL_READ_PCS,PC+1)
LIFETIMES=('recent-version-retained','after-unrelated-version-turnover')

RULES=('short-experience-prepared','normally-learned-long-opposed-identities','fresh-owned-sources-once',
    'qualified-reward','selective-penalty-to-lower-bound','lower-bound-still-corrects-direction',
    'three-actual-read-ages','other-identity-preserved-in-cohort','base-agreement-lower-holds',
    'reverse-and-recover-protection','upper-bound-reward-holds','base-agreement-upper-holds',
    'both-provider-consumers','all-protection-effects-preserved','immutable-originals','actual-feedback-cadence',
    'declared-consumer-lifetime')


@dataclass(frozen=True,slots=True)
class Step:
    ordinal:int
    owner:int
    phase:str
    base:int
    actual:int
    old:tuple
    new:tuple
    tables:tuple

    @property
    def history(self):return 0
    @property
    def indices(self):return (READ_PCS[self.owner]%512,)*2
    @property
    def provider(self):return 1 if self.old[1] is not None else 0 if self.old[0] is not None else None
    @property
    def before(self):return None if self.provider is None else self.old[self.provider]
    @property
    def expected(self):
        return (0,None,None,None) if self.before is None else (1,self.provider,self.before.counter,self.before.taken)
    @property
    def changes(self):
        return tuple((table*512+self.indices[table],0 if old is None else old.useful,new.useful)
            for table,(old,new) in enumerate(zip(self.old,self.new,strict=True))
            if new is not None and new.useful!=(0 if old is None else old.useful))

    def cell(self,table):
        return dict(valid=1,data_valid=1,index=self.indices[table],tag=tag(PC,Context(),table),
                    position=POSITION,counter=self.new[table].counter)


@dataclass(frozen=True,slots=True)
class Program:
    first:int
    mode:str
    lifetime:str='recent-version-retained'
    rules=RULES
    cohort_history=0
    read_pcs=READ_PCS
    phase_rules={'allocate':'short-experience-prepared','promote':'normally-learned-long-opposed-identities',
        'reward-3':'qualified-reward','penalty-3':'selective-penalty-to-lower-bound',
        'base-agreement-lower':'base-agreement-lower-holds','recover-3':'reverse-and-recover-protection',
        'upper-hold':'upper-bound-reward-holds','base-agreement-upper':'base-agreement-upper-holds'}

    def __post_init__(self):
        if type(self.first) is not int or self.first not in (0,1) or self.mode not in MODES or self.lifetime not in LIFETIMES:
            raise ValueError('declared correction identity and communication cadence required')
    @property
    def label(self):return ('not-taken-first' if self.first==0 else 'taken-first')+'.'+self.mode+'.'+self.lifetime
    @property
    def cohort_owners(self):return (1-self.first,self.first)*3+(1-self.first,)

    @property
    def groups(self):
        states=[[None,None],[None,None],[None,None]];result=[];ordinal=0
        recipe=[('allocate',(0,1),'cold'),('promote',(0,1),'promote')]
        recipe.extend((f'reward-{i+1}',(0,1),'reward') for i in range(3))
        recipe.extend((f'penalty-{i+1}',(0,1),'penalty') for i in range(3))
        recipe.extend((('lower-boundary',(self.first,),'penalty'),('other-lower-boundary',(1-self.first,),'penalty'),
                       ('base-agreement-lower',(0,1),'agreement')))
        recipe.extend((f'recover-{i+1}',(0,1),'reward') for i in range(3))
        recipe.extend((('upper-hold',(0,1),'reward'),('base-agreement-upper',(0,1),'agreement')))
        if self.lifetime=='after-unrelated-version-turnover':
            recipe.extend((('unrelated-short',(2,),'cold'),('unrelated-promotion',(2,),'promote')))
            recipe.extend((f'unrelated-reward-{i+1}',(2,),'reward') for i in range(SHADOW_CAPACITY-1))
        for phase,owners,event in recipe:
            group=[]
            for owner in owners:
                old=tuple(states[owner]);new=list(old)
                long_direction=owner if owner in (0,1) else 0
                if event=='cold':
                    base,actual=long_direction,1-long_direction;new[0]=ProtectionState(4 if actual else 3,1);tables=(0,)
                elif event=='promote':
                    base=actual=long_direction
                    new[0]=old[0].feedback(predicted=old[0].taken,base=base,actual=actual)
                    new[1]=ProtectionState(4 if actual else 3,2);tables=(0,1)
                else:
                    actual=1-old[1].taken if event=='penalty' else old[1].taken
                    base=old[1].taken if event=='agreement' else 1-old[1].taken
                    new[1]=old[1].feedback(predicted=old[1].taken,base=base,actual=actual);tables=(1,)
                step=Step(ordinal,owner,phase,base,actual,old,tuple(new),tables)
                states[owner]=new;group.append(step);ordinal+=1
            result.append(tuple(group))
        return tuple(result)

    @property
    def steps(self):return tuple(step for group in self.groups for step in group)
    @property
    def boundary(self):return next(step for step in self.steps if step.phase=='lower-boundary')
    @property
    def expected_tick_failures(self):
        count=sum(step.provider==1 and step.actual!=step.before.taken for step in self.steps)
        return count,count
    @property
    def expected_feedback(self):return len(self.steps)

    @staticmethod
    def read_indices(owner):return (READ_PCS[owner]%512,)*2

    def protection_after(self,count):
        if type(count) is not int or not 0<=count<=len(self.steps):raise ValueError('declared learning prefix required')
        result=[0]*1024
        for step in self.steps[:count]:
            for table,state in enumerate(step.new):
                if state is not None:result[table*512+step.indices[table]]=state.useful
        return tuple(result)

    def cohort_expected(self,owner,relation):
        if relation not in ('before','same-boundary','after'):raise ValueError('actual read/effect relation required')
        prior=next(step for step in reversed(self.steps[:self.boundary.ordinal]) if step.owner==owner)
        state=self.boundary.new[1] if owner==self.first and relation=='after' else prior.new[1]
        return 1,1,state.counter,state.taken

    def final_consumers(self,owner):
        last=next(step for step in reversed(self.steps) if step.owner==owner)
        return tuple((history,table,last.new[table].counter,last.new[table].taken) for history,table in ((0,1),(64,0)))

    def state(self):
        return dict(first=self.first,mode=self.mode,read_pcs=READ_PCS,match_pc=PC,match_history=0,
            lifetime=self.lifetime,
            steps=len(self.steps),boundary_ordinal=self.boundary.ordinal,cohort_owners=self.cohort_owners,
            provider='long-after-real-short-misprediction',each_original_teaches_once=True,
            physical_enumeration=False,maintenance_claimed=False,full_FTQ_reachability_claimed=False)
