"""Two executable loop occurrences, independent feedback order and read views."""
from dataclasses import dataclass
from bpuverify.bpu.model.joint_direction_learning import Program as JointProgram
from bpuverify.sc.model.semantic import way,bias_feature
from bpuverify.sc.transaction.types import ScBaseBranch

BASE_PROFILES=tuple(stage+'.'+result+'.'+order for stage in ('early-valid','steady')
    for result in ('continue','exit') for order in ('old-first','young-first'))
PROFILES=BASE_PROFILES+tuple(p+'.trained' for p in BASE_PROFILES)
RULES=('valid-nonzero-originals','distinct-adjacent-iterations','original-qualification',
    'live-original-history','submissions-before-await','one-acceptance-per-original',
    'both-learners-enabled','actual-learning-overlap','complete-TAGE-effects',
    'complete-five-family-effects','submitted-order-preserved','shared-read-view',
    'private-experience-independent','fresh-consumers','no-effect-before-acceptance',
    'all-original-evidence-preserved')


@dataclass(frozen=True,slots=True)
class Program(JointProgram):
    def __post_init__(self):
        if self.profile not in PROFILES:raise ValueError('declared loop stage, executable outcome and arrival order required')
    @property
    def overlap(self):return False  # Predictions pause; backend learning overlaps.
    @property
    def iterations(self):return self.old_iteration,self.old_iteration+1
    @property
    def trained(self):return self.profile.endswith('.trained')
    @property
    def truths(self):return True,self.profile.split('.')[1]=='continue'
    @property
    def arrival_order(self):return (1,0) if self.profile.split('.')[2]=='young-first' else (0,1)
    @property
    def arrival_truths(self):return tuple(self.truths[i] for i in self.arrival_order)
    @property
    def fresh_counter(self):
        value=6
        for taken in self.arrival_truths:value=max(0,min(7,value+(1 if taken else -1)))
        return value
    def expected_weights(self,iteration,*,serial=False):
        if iteration not in self.iterations:raise ValueError('one of the two declared original iterations required')
        owner=self.iterations.index(iteration)
        shared=int(self.trained)+(sum(1 if v else -1 for v in self.truths) if serial else (1 if self.arrival_truths[-1] else -1))
        private=int(self.trained and owner==0)+(1 if self.truths[owner] else -1)
        column=way(self.position);bias=4*column+bias_feature(ScBaseBranch(self.position,6))
        return tuple(tuple((private if family==3 else shared) if i==(bias if family==4 else column) else 0
            for i in range(16 if family==4 else 4)) for family in range(5))
    def training_weights(self,iteration):
        if iteration not in self.iterations:raise ValueError('one declared original iteration required')
        column=way(self.position);bias=4*column+bias_feature(ScBaseBranch(self.position,6))
        return tuple(tuple(int(self.trained and (family!=3 or iteration==self.iterations[0]))
            if i==(bias if family==4 else column) else 0
            for i in range(16 if family==4 else 4)) for family in range(5))
    def state(self):
        return dict(profile=self.profile,original_iterations=self.iterations,
            trained_nonzero_experience=self.trained,
            actual_outcomes=self.truths,arrival_order=self.arrival_order,original_counter=6,
            fresh_counter=self.fresh_counter,SC_training_reads_own_their_view=True,
            serialized_shared_atomicity_required=False,prediction_overlap=False,
            learning_overlap_required=True,physical_enumeration=False,complete_FTQ=False)
