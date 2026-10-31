"""Two old outcomes wait while unrelated younger loop occurrences progress."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.joint_originals import Program as OriginalProgram,PROFILES as ORIGINAL_PROFILES,RULES as ORIGINAL_RULES

PROFILES=tuple(p for p in ORIGINAL_PROFILES if p.endswith('.trained'))
NEW_RULES=('queued-before-prediction-wait','head-stall-cannot-train-either',
    'tail-cannot-bypass-head','real-predictions-progress-while-held',
    'actual-conflict-release','all-stream-numeric-comparisons')
RULES=ORIGINAL_RULES+NEW_RULES


@dataclass(frozen=True,slots=True)
class Program(OriginalProgram):
    def __post_init__(self):
        if self.profile not in PROFILES:raise ValueError('a real nonzero-experience joint-stream lifecycle is required')

    def state(self):
        return dict(super(Program,self).state(),prediction_overlap=True,
            queued_old_results=2,actual_head_conflict_required=True,whole_feedback_wait=True,
            fixed_wait_cycles=False,arbitrary_history_age_claimed=False)
