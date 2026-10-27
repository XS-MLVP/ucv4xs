"""Declared behavior phases reuse ProtectionState, not native signal logic."""
from dataclasses import dataclass
from bpuverify.utage.model.semantic import Context,tag
from bpuverify.utage.model.usefulness_events import ProtectionState
from bpuverify.utage.model.query_identity import PC,POSITION,READ_PCS,MODES

RULES=('normally-learned-opposed-identities','fresh-owned-sources-once','qualified-reward',
    'selective-penalty-to-lower-bound','lower-bound-still-corrects-direction','three-actual-read-ages',
    'other-identity-preserved-in-cohort','base-agreement-lower-holds','reverse-and-recover-protection',
    'upper-bound-reward-holds','base-agreement-upper-holds','both-provider-consumers',
    'all-protection-effects-preserved','immutable-originals','actual-feedback-cadence')


@dataclass(frozen=True)
class Step:
    ordinal:int
    owner:int
    phase:str
    history:int
    base:int
    actual:int
    before:ProtectionState|None
    after:ProtectionState
    companion_allocation:bool=False

    @property
    def indices(self):return self.owner*256,self.owner*256
    @property
    def expected(self):
        return (0,None,None,None) if self.before is None else (1,0,self.before.counter,self.before.taken)
    @property
    def counter_cell(self):return dict(valid=1,data_valid=1,index=self.indices[0],tag=0,position=POSITION,counter=self.after.counter)
    @property
    def companion_cell(self):
        return dict(valid=1,data_valid=1,index=self.indices[1],tag=tag(PC,Context.from_recent(self.history),1),
            position=POSITION,counter=4 if self.actual else 3)
    @property
    def changes(self):
        old=0 if self.before is None else self.before.useful
        result=[] if old==self.after.useful else [(self.indices[0],old,self.after.useful)]
        if self.companion_allocation:result.append((512+self.indices[1],0,2))
        return tuple(sorted(result))


@dataclass(frozen=True)
class Program:
    first:int
    mode:str

    def __post_init__(self):
        if type(self.first) is not int or self.first not in (0,1) or self.mode not in MODES:
            raise ValueError('one first correction owner and an existing feedback cadence required')
    @property
    def label(self):return ('taken-first' if self.first==0 else 'not-taken-first')+'.'+self.mode

    @property
    def groups(self):
        states=[None,None];companions=[False,False];groups=[];number=0
        recipe=[('allocate',(0,1),'cold')]
        recipe.extend((f'reward-{i+1}',(0,1),'reward') for i in range(3))
        recipe.extend((f'penalty-{i+1}',(0,1),'penalty') for i in range(3))
        recipe.extend((('lower-boundary',(self.first,),'penalty'),('other-lower-boundary',(1-self.first,),'penalty'),
            ('base-agreement-lower',(0,1),'agreement')))
        recipe.extend((f'recover-{i+1}',(0,1),'reward') for i in range(3))
        recipe.extend((('upper-hold',(0,1),'reward'),('base-agreement-upper',(0,1),'agreement')))
        for phase,owners,event in recipe:
            group=[]
            for owner in owners:
                old=states[owner];history=64 if companions[owner] else 0
                if event=='cold':
                    base,actual=owner,1-owner
                    new=ProtectionState(4 if actual else 3,1)
                else:
                    actual=1-old.taken if event=='penalty' else old.taken
                    base=old.taken if event=='agreement' else 1-old.taken
                    new=old.feedback(predicted=old.taken,base=base,actual=actual)
                allocate=phase=='penalty-1'
                group.append(Step(number,owner,phase,history,base,actual,old,new,allocate))
                states[owner]=new;companions[owner]|=allocate;number+=1
            groups.append(tuple(group))
        return tuple(groups)

    @property
    def steps(self):return tuple(step for group in self.groups for step in group)
    @property
    def boundary(self):return next(step for step in self.steps if step.phase=='lower-boundary')
    @property
    def cohort_owners(self):return (1-self.first,self.first)*3+(1-self.first,)

    def protection_after(self,count):
        if type(count) is not int or not 0<=count<=len(self.steps):raise ValueError('bounded declared learning prefix required')
        values=[0]*1024
        for step in self.steps[:count]:
            values[step.indices[0]]=step.after.useful
            if step.companion_allocation:values[512+step.indices[1]]=2
        return tuple(values)

    def short_states_after(self,count):
        states=[None,None]
        for step in self.steps[:count]:states[step.owner]=step.after
        return tuple(states)

    def cohort_expected(self,owner,relation):
        if relation not in ('before','same-boundary','after'):raise ValueError('actual read/effect relation required')
        state=self.boundary.after if owner==self.first and relation=='after' else self.short_states_after(self.boundary.ordinal)[owner]
        return 1,0,state.counter,state.taken

    def state(self):return dict(first=self.first,mode=self.mode,read_pcs=READ_PCS,match_pc=PC,
        steps=len(self.steps),boundary_ordinal=self.boundary.ordinal,cohort_owners=self.cohort_owners,
        each_original_teaches_once=True,physical_enumeration=False,maintenance_claimed=False)
