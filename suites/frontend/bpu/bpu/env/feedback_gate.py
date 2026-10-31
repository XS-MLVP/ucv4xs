"""Public driver admission; complete immutable input transport."""
from copy import deepcopy
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.env.main_service import MainProgram, branch
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.checker.feedback_gate import FeedbackChecker
from suites.frontend.bpu.bpu.bundle.feedback_gate import full_input_binding


class FeedbackObservation(PipelineObservation):
    def __init__(self, agent):
        super().__init__(agent,sources=BranchTargetSources(),binding_factory=full_input_binding)
        self.checker=FeedbackChecker(sources=BranchTargetSources(),capacity=8)


class FeedbackProgram(MainProgram):
    def __init__(self,*args):
        super().__init__(*args)
        self.submissions=[]

    def prepare_input(self, source, target):
        original=self.checker.receipt_window(source)
        tx=BpuBatchTraining(source.prediction.start_pc,deepcopy(source.meta.resolve),
            (branch(1,target,3,wrong=True),))
        self.checker.gate.prepare(original,tx,receipt_metadata=source.meta.resolve)
        return tx

    async def send_prepared(self, source, tx):
        checker=self.checker
        before=len(checker.actual_inputs)
        def admission(transaction):
            checker.raise_failure()
            checker.gate.admit(transaction)
            checker.plan_feedback(source,transaction)
            return True
        try:
            with self.agent.training_driver.admit_when(admission):
                handle=self.agent.training_driver.send(tx)
                self.submissions.append(handle)
                event=await handle
        except BaseException:
            if checker.gate.pending is not None and not checker.gate.pending.launched:
                checker.gate.cancel_unlaunched()
            raise
        checker.raise_failure()
        assert len(checker.actual_inputs)==before+1
        assert checker.actual_inputs[-1]['tick']==event.tick
        await self.pause()
        return event


