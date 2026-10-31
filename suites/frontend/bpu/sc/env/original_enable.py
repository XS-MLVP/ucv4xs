"""Enable/feedback transitions remain inside driver/monitor support."""
from suites.frontend.bpu.sc.model.boundary import expected_feedback,observed_feedback
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel
from suites.frontend.bpu.sc.env.eligibility import EligibilityEnv
from suites.frontend.bpu.sc.checker.original_enable import EnableChecks
from suites.frontend.bpu.sc.monitor.original_enable import EnableInputMonitor


class EnableEnv(EligibilityEnv):
    def __init__(self,agent,program,coverage):
        self.agent,self.program,self.coverage=agent,program,coverage
        self.checks=EnableChecks(program,coverage)
        self.thresholds=ScThresholdModel.for_default()
        self.inputs=EnableInputMonitor(agent)

    async def disable_old_outcomes_and_reopen(self):
        agent,program,checks=self.agent,self.program,self.checks
        originals=[(owner,agent.submit_predict_branches(owner.pc,owner.layout())) for owner in program.owners]
        await agent.drain_predictions()
        for owner,transfer in originals:
            checks.active_original(owner,transfer,await transfer,self.inputs.input_for(transfer))
        await agent.set_enabled(False)
        for owner in program.owners:
            transfer=agent.submit_predict_branches(owner.pc,owner.layout())
            prediction=await transfer
            checks.disabled_query(owner,transfer,prediction,self.inputs.input_for(transfer))
        branch_count=len(agent.ports.training.bits.branches)
        fold_count=len(agent.ports.training.bits.path_history)
        async with agent.observe_feedback() as frames:
            for owner in program.owners:
                actual,expected=checks.old_feedback(owner)
                effect=self.thresholds.apply(expected,enabled=False)
                checks.check((),effect.qualifying_slots,'disabled original outcome produces no qualified threshold vote')
                checks.check(effect.before,effect.after,'disabled outcome leaves independent thresholds unchanged')
                start=len(frames)
                await agent.train_batch(actual)
                observed=frames[start:]
                checks.check((expected_feedback(expected,branch_count=branch_count,fold_count=fold_count),),
                    tuple(observed_feedback(frame.value) for frame in observed),
                    'complete actual old feedback is present even though learning is disabled')
                checks.ignored_old_feedback(owner,observed[0].event.tick,
                    actual_enabled=self.inputs.enabled_at(observed[0].event.tick))
                await agent.check_thresholds(self.thresholds.values)
        await agent.set_enabled(True)
        for owner in program.owners:
            transfer=agent.submit_predict_branches(owner.pc,owner.layout())
            prediction=await transfer
            checks.restored_consumer(owner,transfer,prediction,self.inputs.input_for(transfer))
