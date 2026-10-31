"""Declared instruction experience; existing models own all predictor algorithms."""
from suites.frontend.bpu.models.configuration import SC_TABLES, TAGE_TABLES

from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.common_history import LOOKUP_WINDOW_CAPACITY,GHR_WIDTH
from suites.frontend.bpu.bpu.model.path_history import SHIFT
from suites.frontend.bpu.bpu.model.loop_iteration import PC,POSITION,MAX_ITERATIONS
from suites.frontend.bpu.bpu.model.pipeline import Outcome
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.tage.model.semantic import HISTORIES
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel

PROFILES=tuple(stage+'.'+mode for stage in ('early-valid','steady') for mode in ('serial','overlap'))
RULES=('valid-nonzero-original','owned-five-family-read','cold-unused-control',
    'distinct-real-teaching','strong-loop-consumer','younger-distinct-iteration',
    'original-qualification','complete-original-admission','five-family-effects',
    'fresh-old-iteration-consumer','private-younger-loop-preserved','all-original-evidence-preserved')


@dataclass(frozen=True,slots=True)
class Program:
    profile:str
    a:int=0x40000000

    def __post_init__(self):
        if self.profile not in PROFILES:raise ValueError('declared real loop stage and feedback mode required')
    b=PC
    position=POSITION
    exit_position=POSITION+1
    provider_counter=5
    recovery_offset=0
    @property
    def d(self):return self.b
    @property
    def overlap(self):return self.profile.endswith('.overlap')
    @property
    def old_iteration(self):
        complete_ancestry=(max(HISTORIES)+SHIFT-1)//SHIFT+LOOKUP_WINDOW_CAPACITY
        return complete_ancestry+(GHR_WIDTH+1 if self.profile.startswith('steady.') else 0)
    @property
    def young_iteration(self):return self.old_iteration+GHR_WIDTH+1
    @property
    def teaching_count(self):
        # All five weights retain enough authority after ONE genuine error.
        # Confidence5 uses the normal five-bit threshold shift.
        threshold=ScThresholdModel.for_default().initial[0]
        return next(votes for votes in range(1,32) if SC_TABLES*(2*(votes-1)+1)>threshold//32)
    def outcome(self,source,prediction,taken):
        if type(taken) is not bool:raise TypeError('declared original conditional outcome required')
        branch=prediction.branch
        wrong=(branch.position,branch.target,branch.kind,branch.taken)!=(self.position,self.b,Kind.CONDITIONAL,True) if taken else branch.taken
        return Outcome(self.position,self.b,Kind.CONDITIONAL,taken,mispredict=bool(wrong))
    def require_iteration(self,value,*,young=False):
        expected=self.young_iteration if young else self.old_iteration
        if type(value) is not int or value!=expected or not 0<value<=MAX_ITERATIONS:
            raise ValueError('exact declared nonzero original loop iteration required')
        return value
    def state(self):
        return dict(profile=self.profile,old_iteration=self.old_iteration,young_iteration=self.young_iteration,
            teaching_originals=self.teaching_count,concurrent_predictions=self.overlap,
            return_through_real_loop_exit=True,entry_checkpoint_reused_after_expiry=False,
            private_loop_experience=True,shared_features_may_change=True,physical_enumeration=False,
            new_predictor_algorithm=False,complete_FTQ=False)
