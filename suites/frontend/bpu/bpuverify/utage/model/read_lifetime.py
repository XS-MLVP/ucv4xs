"""Discriminating branch-version changes, not physical coordinate cases."""
from dataclasses import dataclass
from bpuverify.utage.model.semantic import Context,indices,tag
from bpuverify.utage.model.usefulness_events import ProtectionState,MODES

PC,POSITION,NEIGHBOR=0x40000000,5,0x40000002
PROFILES=('provider-promotion','different-identity-replacement')
RELATIONS=('read-with-write','read-after-write')
RULES=('normally-learned-distinct-prestate','complete-original-feedback',
    'actual-read-effect-relation','original-read-not-rebound','declared-response-version',
    'fresh-new-version-consumers','all-other-protection-and-neighbor-preserved','immutable-originals')


@dataclass(frozen=True)
class Program:
    profile:str
    relation:str

    def __post_init__(self):
        if self.profile not in PROFILES or self.relation not in RELATIONS:
            raise ValueError('declared version change and read relation required')

    @property
    def history(self):return 0 if self.profile=='provider-promotion' else 64
    @property
    def teacher_pc(self):return PC if self.profile=='provider-promotion' else PC+1024
    @property
    def actual(self):return 0 if self.profile=='provider-promotion' else 1
    @property
    def old_counter(self):return 4 if self.profile=='provider-promotion' else 3
    @property
    def old(self):return 1,0,self.old_counter,int(self.old_counter>=4)
    @property
    def new(self):return (1,1,3,0) if self.profile=='provider-promotion' else (0,None,None,None)
    @property
    def expected(self):return self.old if self.relation=='read-with-write' else self.new

    def protection(self,*,after):
        values=[0]*1024
        values[indices(NEIGHBOR,Context())[0]]=1
        index=indices(PC,Context())[0]
        if self.profile=='provider-promotion':
            values[index]=0 if after else 1
            if after:values[512+indices(PC,Context())[1]]=2
        else:
            values[index]=int(after)
            values[512+indices(PC,Context())[1]]=2
        return tuple(values)

    def changes(self):
        return tuple((index,old,new) for index,(old,new) in enumerate(zip(
            self.protection(after=False),self.protection(after=True),strict=True)) if old!=new)

    def state(self):
        return dict(profile=self.profile,relation=self.relation,pc=PC,history=self.history,
            teacher_pc=self.teacher_pc,teacher_actual=self.actual,old=self.old,new=self.new,
            expected_response=self.expected,physical_enumeration=False)


REBUILD_PROFILES=('old-NT-current-T','old-T-current-NT')
REBUILD_RULES=('real-distinct-originals','same-short-row-distinct-complete-tags',
    'normally-released-original','strong-different-current-owner',
    'old-source-counter-reconstruction','second-old-source-counter-reconstruction',
    'actual-requested-feedback-cadence','both-complete-retag-writes',
    'original-allocation-view-survives-overlap','fresh-short-and-long-consumers',
    'neighbor-and-complete-protection-preserved','immutable-originals')


@dataclass(frozen=True)
class RebuildSource:
    owner:int
    history:int
    base:int
    counter:int|None

    @property
    def pc(self):return (PC,PC+4,NEIGHBOR)[self.owner]
    @property
    def read_pc(self):return NEIGHBOR if self.owner==2 else PC
    @property
    def indices(self):return indices(self.read_pc,Context.from_recent(self.history))
    @property
    def expected(self):return (0,None,None,None) if self.counter is None else (1,0,self.counter,int(self.counter>=4))


@dataclass(frozen=True)
class RebuildStep:
    ordinal:int
    name:str
    source:RebuildSource
    actual:int
    before:ProtectionState|None
    after:ProtectionState
    companion:bool=False
    companion_useful_before:int=0

    @property
    def changes(self):
        old=0 if self.before is None else self.before.useful
        result=[] if old==self.after.useful else [(self.source.indices[0],old,self.after.useful)]
        if self.companion and self.companion_useful_before!=2:
            result.append((512+self.source.indices[1],self.companion_useful_before,2))
        return tuple(sorted(result))

    def cell(self,table):
        counter=self.after.counter if table==0 else 4 if self.actual else 3
        return dict(valid=1,data_valid=1,index=self.source.indices[table],
            tag=tag(self.source.pc,Context.from_recent(self.source.history),table),position=POSITION,counter=counter)


@dataclass(frozen=True)
class LateReplacementProgram:
    profile:str
    mode:str

    def __post_init__(self):
        if self.profile not in REBUILD_PROFILES or self.mode not in MODES:
            raise ValueError('two declared opposed original/current directions and serial/adjacent feedback required')

    @property
    def inverse(self):return self.profile==REBUILD_PROFILES[1]
    @property
    def label(self):return self.profile+'.'+self.mode
    @property
    def old_a(self):return RebuildSource(0,128,1-int(self.inverse),4 if self.inverse else 3)
    @property
    def old_b(self):return RebuildSource(1,128,int(self.inverse),0 if self.inverse else 7)

    @property
    def steps(self):
        # A fixed branch lifetime, not a second table algorithm or coordinate sweep.
        rows=[('neighbor',RebuildSource(2,0,1,None),0,None,ProtectionState(3,1),False),
            ('A-enter',RebuildSource(0,0,0,None),1,None,ProtectionState(4,1),False),
            ('A-release',RebuildSource(0,0,0,4),0,ProtectionState(4,1),ProtectionState(3,0),True)]
        if self.inverse:
            rows.append(('A-recover',RebuildSource(0,64,1,3),1,ProtectionState(3,0),ProtectionState(4,0),True))
        b_taken=1-int(self.inverse)
        initial=4 if b_taken else 3
        rows.append(('B-enter',RebuildSource(1,128,1-b_taken,None),b_taken,
            ProtectionState(self.old_a.counter,0),ProtectionState(initial,1),False))
        current=ProtectionState(initial,1)
        for number in range(3):
            after=current.feedback(predicted=b_taken,base=1-b_taken,actual=b_taken)
            rows.append((f'B-reward-{number+1}',RebuildSource(1,128,1-b_taken,current.counter),
                b_taken,current,after,False))
            current=after
        rebuilt=ProtectionState(3 if self.inverse else 4,2)
        rows.append(('old-A-return',self.old_a,b_taken,current,rebuilt,True))
        rows.append(('old-B-return',self.old_b,1-b_taken,rebuilt,ProtectionState(1 if self.inverse else 6,1),
            self.mode=='adjacent',2))
        return tuple(RebuildStep(ordinal,*row) for ordinal,row in enumerate(rows))

    def protection_after(self,count):
        if type(count) is not int or not 0<=count<=len(self.steps):raise ValueError('complete declared feedback prefix required')
        result=[0]*1024
        for step in self.steps[:count]:
            result[step.source.indices[0]]=step.after.useful
            if step.companion:result[512+step.source.indices[1]]=2
        return tuple(result)

    def consumers(self,*,after_a):
        a_counter=3 if self.inverse else 4
        b_counter=1 if self.inverse else 6
        result=[(RebuildSource(0,256,0,None),(1,0,a_counter,int(a_counter>=4)) if after_a else (0,None,None,None)),
            (RebuildSource(1,256,0,None),(0,None,None,None) if after_a else (1,0,b_counter,int(b_counter>=4))),
            (RebuildSource(0,128,0,None),(1,1,a_counter,int(a_counter>=4)) if after_a or self.mode=='serial' else (0,None,None,None)),
            (RebuildSource(2,0,1,None),(1,0,3,0))]
        if not after_a:
            result.append((RebuildSource(1,128,0,None),(1,0,b_counter,int(b_counter>=4)) if self.mode=='serial'
                else (1,1,4 if self.inverse else 3,int(self.inverse))))
        return tuple(result)

    def state(self):
        return dict(profile=self.profile,mode=self.mode,feedbacks=len(self.steps),
            old_A=self.old_a.expected,old_B=self.old_b.expected,read_pc=PC,match_pcs=(PC,PC+4),
            complete_short_tags=tuple(tag(source.pc,Context.from_recent(source.history),0) for source in (self.old_a,self.old_b)),
            physical_enumeration=False,integrated_FTQ_claimed=False,persistence_after_retirement_claimed=False)
