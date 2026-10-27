"""Existing agent protocol support; no scheduler or signal details in cases."""
from bpuverify.sc.model.boundary import expected_feedback,observed_feedback
from bpuverify.sc.model.threshold import ScThresholdModel
from bpuverify.sc.checker.eligibility import EligibilityChecks
from bpuverify.sc.monitor.eligibility import EligibilityInputMonitor


class EligibilityEnv:
    def __init__(self,agent,program,coverage):
        self.agent,self.program,self.coverage=agent,program,coverage
        self.checks=EligibilityChecks(program,coverage)
        self.thresholds=ScThresholdModel()
        self.inputs=EligibilityInputMonitor(agent)

    async def __aenter__(self):
        self.inputs.start(self.agent._execution)
        return self

    async def __aexit__(self,exc_type,exc,traceback):
        await self.inputs.aclose()

    async def learn_originals(self):
        agent,program,checks,thresholds=self.agent,self.program,self.checks,self.thresholds
        await agent.reset()
        await agent.check_thresholds(thresholds.values)
        checks.check(program.thresholds(checks.counts),thresholds.values,'independent initial thresholds')
        pending=[(owner,agent.submit_predict_branches(owner.pc,owner.layout()))
            for owner in program.owners for _ in range(program.warm_votes)]
        await agent.drain_predictions()
        for owner,transfer in pending:
            prediction=await transfer
            checks.cold_source(owner,transfer,prediction,self.inputs.input_for(transfer))
        branch_count=len(agent.ports.training.bits.branches)
        fold_count=len(agent.ports.training.bits.path_history)
        async with agent.observe_feedback() as frames:
            for _,transfer in pending:
                actual,expected=checks.feedback(transfer.sequence_id)
                effect=thresholds.apply(expected)
                checks.check((0,),effect.qualifying_slots,'each original source produces a genuine qualified vote')
                start=len(frames)
                await agent.train_batch(actual)
                observed=frames[start:]
                checks.check((expected_feedback(expected,branch_count=branch_count,fold_count=fold_count),),
                    tuple(observed_feedback(frame.value) for frame in observed),
                    'complete actual feedback equals the independent original-source intention')
                checks.accepted_feedback(transfer.sequence_id,observed[0].event.tick)
                checks.check(program.thresholds(checks.counts),thresholds.values,
                             'closed-form warm thresholds and independent feedback ledger agree')
                await agent.check_thresholds(thresholds.values)
        checks.warm_complete()

    async def consume_qualification_changes(self):
        agent,program,checks=self.agent,self.program,self.checks
        before=len(agent.training_observations)
        if program.mode=='pipelined':
            queries=[(probe,agent.submit_predict_branches(probe.owner.pc,probe.owner.layout(probe.gate)))
                for probe in program.probes]
            await agent.drain_predictions()
            for probe,transfer in queries:
                prediction=await transfer
                checks.query(probe,transfer,prediction,self.inputs.input_for(transfer))
        else:
            for probe in program.probes:
                transfer=agent.submit_predict_branches(probe.owner.pc,probe.owner.layout(probe.gate))
                prediction=await transfer
                checks.query(probe,transfer,prediction,self.inputs.input_for(transfer))
        checks.check(before,len(agent.training_observations),'qualification changes never relearn or erase weights')
        await agent.check_thresholds(self.thresholds.values)

    async def prove_retained_strength(self):
        agent,program,checks=self.agent,self.program,self.checks
        branch_count=len(agent.ports.training.bits.branches)
        fold_count=len(agent.ports.training.bits.path_history)
        # A frozen number of real opposite outcomes must cross each family's
        # zero boundary at the exact step, then actually override the unchanged
        # base in the other direction. A same-sign corrupted weight cannot
        # hide behind a final equal-looking "used" bit.
        async with agent.observe_feedback() as frames:
            for owner in program.owners:
                for _ in range(program.reversal_steps(owner)):
                    transfer=agent.submit_predict_branches(owner.pc,owner.layout())
                    prediction=await transfer
                    checks.reverse_source(owner,transfer,prediction,self.inputs.input_for(transfer))
                    actual,expected=checks.feedback(transfer.sequence_id,reverse=True)
                    effect=self.thresholds.apply(expected)
                    checks.check((0,),effect.qualifying_slots,'each fresh opposite outcome genuinely changes learning')
                    start=len(frames)
                    await agent.train_batch(actual)
                    observed=frames[start:]
                    checks.check((expected_feedback(expected,branch_count=branch_count,fold_count=fold_count),),
                        tuple(observed_feedback(frame.value) for frame in observed),
                        'actual opposite feedback belongs to its original prediction')
                    checks.accepted_feedback(transfer.sequence_id,observed[0].event.tick,reverse=True)
                    checks.check(program.thresholds(checks.counts,checks.reversals),self.thresholds.values,
                                 'independent threshold ledger follows the declared opposite outcomes')
                    await agent.check_thresholds(self.thresholds.values)
                    consumer=agent.submit_predict_branches(owner.pc,owner.layout())
                    prediction=await consumer
                    checks.reverse_consumer(owner,consumer,prediction,self.inputs.input_for(consumer))

    def finish(self):
        self.checks.finish()
        self.agent.reference.raise_failure()
