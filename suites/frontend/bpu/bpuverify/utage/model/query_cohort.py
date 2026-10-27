"""One semantic cohort around learning, then fresh-source version turnover."""
from dataclasses import dataclass
from bpuverify.utage.model.semantic import Context,indices,tag
from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from bpuverify.utage.model.read_lifetime import Program as OriginalProgram,PC,POSITION,NEIGHBOR
from bpuverify.utage.model.ancestor_lifetime import MATCH_PC,MATCH_HISTORY

PROFILES=('counter-reinforcement','provider-promotion','identity-replacement')
ANCESTRIES=('own-context','distinct-ancestors')
COHORT_SIZE=5
RULES=('normally-learned-prestate','adjacent-overlapping-originals','three-actual-read-ages',
    'each-response-owns-original-read','complete-original-feedbacks-once',
    'actual-version-retention-turnover','fresh-latest-consumers',
    'all-protection-and-neighbor-preserved','completed-originals-stay-immutable')


@dataclass(frozen=True)
class Program:
    profile:str
    ancestry:str

    def __post_init__(self):
        if self.profile not in PROFILES or self.ancestry not in ANCESTRIES:
            raise ValueError('declared semantic version change and query ancestry required')
        if self.ancestry=='distinct-ancestors':
            if indices(self.match_pc,self.match_context)==self.read_indices:
                raise ValueError('distinct ancestry must distinguish own and original read indices')
            if any(tag(self.match_pc,self.match_context,t)!=tag(PC,self.read_context,t) for t in range(2)):
                raise ValueError('the chosen match ancestry must preserve the declared original identity')

    @property
    def legacy(self):return OriginalProgram('different-identity-replacement' if self.profile=='identity-replacement'
        else 'provider-promotion','read-with-write')
    @property
    def label(self):return self.profile+'.'+self.ancestry
    @property
    def history(self):return self.legacy.history
    @property
    def read_context(self):return Context.from_recent(self.history)
    @property
    def read_indices(self):return indices(PC,self.read_context)
    @property
    def match_pc(self):return PC if self.ancestry=='own-context' else MATCH_PC
    @property
    def match_history(self):
        # The established PC/history discriminator preserves tags relative to
        # history zero. Folded-history XOR is linear, so retain the original
        # query history as well; replacement starts with a nonzero history.
        return self.history if self.ancestry=='own-context' else self.history^MATCH_HISTORY
    @property
    def match_context(self):return Context.from_recent(self.match_history)
    @property
    def teacher_pc(self):return self.legacy.teacher_pc
    @property
    def target_table(self):return int(self.profile=='provider-promotion')
    @property
    def target_index(self):return indices(self.teacher_pc,self.read_context)[self.target_table]
    @property
    def actual(self):return int(self.profile!='provider-promotion')
    @property
    def teacher_base(self):return 1-self.actual
    @property
    def old(self):return self.legacy.old
    @property
    def new(self):
        return (1,0,5,1) if self.profile=='counter-reinforcement' else self.legacy.new

    def counter(self,additional_versions):
        if type(additional_versions) is not int or not 0<=additional_versions<=SHADOW_CAPACITY:
            raise ValueError('one declared retention turnover requires a bounded version count')
        first={'counter-reinforcement':5,'provider-promotion':3,'identity-replacement':4}[self.profile]
        return min(7,first+additional_versions) if self.actual else max(0,first-additional_versions)

    def teacher_expected(self,additional_versions):
        value=self.counter(additional_versions)
        return 1,self.target_table,value,int(value>=4)

    def query_expected(self,relation):
        if relation not in ('before','same-boundary','after'):raise ValueError('actual read/effect relation required')
        return self.new if relation=='after' else self.old

    def final_query(self):
        return (0,None,None,None) if self.profile=='identity-replacement' else self.teacher_expected(SHADOW_CAPACITY)

    def protection(self,phase):
        values=list(self.legacy.protection(after=False))
        if phase=='before':return tuple(values)
        if phase not in ('first-effect','turnover'):raise ValueError('declared protection epoch required')
        if self.profile=='provider-promotion':
            values[self.read_indices[0]]=0
            values[512+self.target_index]=2 if phase=='first-effect' else 3
        elif self.profile=='identity-replacement':
            values[self.target_index]=1 if phase=='first-effect' else 3
        else:values[self.target_index]=2 if phase=='first-effect' else 3
        return tuple(values)

    def first_changes(self):
        return tuple((i,a,b) for i,(a,b) in enumerate(zip(self.protection('before'),
            self.protection('first-effect'),strict=True)) if a!=b)

    def state(self):
        return dict(profile=self.profile,ancestry=self.ancestry,read_pc=PC,read_history=self.history,
            read_indices=self.read_indices,match_pc=self.match_pc,match_history=self.match_history,
            teacher_pc=self.teacher_pc,actual=self.actual,old=self.old,new=self.new,
            cohort_size=COHORT_SIZE,retention_turnover_versions=SHADOW_CAPACITY,
            completed_responses_are_not_claimed_still_inflight=True,physical_enumeration=False)
