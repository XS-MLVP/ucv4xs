"""Reuse complete source/proposal/service checking; retain the first failure."""
from copy import deepcopy
from bpuverify.bpu.checker.direction_turnaround import DirectionTurnaroundChecks
from bpuverify.bpu.model.tage.opposed_learning_pair import PROGRAMS


class OpposedLearningPairChecks(DirectionTurnaroundChecks):
    programs=PROGRAMS

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.compared_consumers={}

    def consume(self,phase,name,source):
        compared=self.profile(source)
        super().consume(phase,name,source)
        self.compared_consumers[phase+'.'+name]=dict(prediction_tick=source.prediction_tick,
            meta_tick=source.meta_tick,compared=deepcopy(compared))

    def snapshot(self):
        # No compare or model mutation while reporting a primary exception.
        return deepcopy(dict(program=self.program.name,phase=self.phase,closed=self.closed,
            accepted_ticks=self.input_ticks,actual_proposals=self.offered,
            actual_services=self.written,expected_remaining_plan=getattr(self,'expected_plan',None),
            consumer_profiles=self.compared_consumers,
            original_meta_ticks=[source.meta_tick for source in getattr(self,'requests',())],
            completed_obligations=sorted(self.completed),
            first_failure_type=None if self.failure is None else type(self.failure).__name__,
            first_failure=None if self.failure is None else str(self.failure),
            original_prediction_values_and_correct_prefix_compared=self.rules[13] in self.completed,
            full_FTQ_source_eligibility_proved=False))
