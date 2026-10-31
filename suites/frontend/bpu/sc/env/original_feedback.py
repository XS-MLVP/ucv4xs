"""Only the driver/monitor environment handles feedback and visibility."""
from suites.frontend.bpu.sc.model.boundary import observed_feedback
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel
from suites.frontend.bpu.sc.env.eligibility import EligibilityEnv
from suites.frontend.bpu.sc.monitor.eligibility import EligibilityInputMonitor
from suites.frontend.bpu.sc.checker.original_feedback import FeedbackChecks
from suites.frontend.bpu.sc.model.original_feedback import expected_offer


class FeedbackEnv(EligibilityEnv):
    def __init__(self,agent,program,coverage):
        self.agent,self.program,self.coverage=agent,program,coverage
        self.checks=FeedbackChecks(program,coverage)
        self.thresholds=ScThresholdModel.for_default()
        self.inputs=EligibilityInputMonitor(agent)

    async def ignore_original_outcomes(self):
        agent,program,checks=self.agent,self.program,self.checks
        branch_count=len(agent.ports.training.bits.branches)
        fold_count=len(agent.ports.training.bits.path_history)
        async with agent.observe_feedback() as frames:
            for owner in program.owners:
                gate=program.rejection_gate
                transfer=agent.submit_predict_branches(owner.pc,owner.layout(gate))
                prediction=await transfer
                checks.rejected_source(owner,transfer,prediction,self.inputs.input_for(transfer))
                actual,expected=checks.rejected_feedback(owner)
                effect=self.thresholds.apply(expected)
                checks.check((),effect.qualifying_slots,'the declared invalid cause produces no threshold learning vote')
                checks.check(effect.before,effect.after,'ignored feedback preserves its exact independent threshold state')
                start=len(frames)
                await agent.train_batch(actual)
                observed=frames[start:]
                checks.check((expected_offer(expected,branch_count=branch_count,fold_count=fold_count),),
                    tuple(observed_feedback(frame.value) for frame in observed),
                    'actual whole ignored feedback retains its original cause, PC, history and metadata')
                checks.accepted_rejection(owner,observed[0].event.tick)
                checks.check(program.thresholds(checks.counts),self.thresholds.values,
                             'ignored outcomes do not advance the closed-form original learning state')
                await agent.check_thresholds(self.thresholds.values)
                consumer=agent.submit_predict_branches(owner.pc,owner.layout())
                prediction=await consumer
                checks.retained_consumer(owner,consumer,prediction,self.inputs.input_for(consumer))
