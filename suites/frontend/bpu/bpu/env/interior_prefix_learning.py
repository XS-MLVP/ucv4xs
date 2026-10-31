"""Use existing async drivers and actual maturity, never a timing delay."""
from suites.frontend.bpu.bpu.env.mixed_visibility import MixedVisibilityService
from suites.frontend.bpu.bpu.model.tage.service import learning_inflight
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining


class LearningService(MixedVisibilityService):
    async def submit_mixed_learning(self):
        if self.checks.program.schedule=='adjacent-acceptance':return await super().submit_mixed_learning()
        self.checks.arm_mixed();requests=tuple((source,self.env.branch_path(outcome)) for source,outcome in
            zip(self.checks.requests[3:],self.checks.program.late_outcomes,strict=True))
        transactions=[]
        for source,branches in requests:
            transaction=BpuBatchTraining(source.prediction.start_pc,source.meta.resolve,tuple(branches))
            self.env.checker.plan_feedback(source,transaction);transactions.append(transaction)
        before=self.env.checker.last_tick;handles=[]
        def healthy():self.monitor.raise_failure();return True
        try:
            for index,transaction in enumerate(transactions):
                handle=self.agent.training_driver.send(transaction);handles.append(handle)
                await self.env.observation.wait('one_complete_prefix_original_accepted',lambda _:healthy() and handle.done())
                if index==0:
                    await self.env.observation.wait('first_actual_complete_prefix_learning_matured',
                        lambda checker:healthy() and len(self.checks.offered)==4 and not learning_inflight(checker.model.sources.tage))
                    self.checks.first_learning_settled(self.env.checker.last_tick)
            ticks=tuple([(await handle).tick for handle in handles])
            receipts={tick:resolution for source,_ in requests for tick,resolution in
                self.env.checker.resolutions_for_source(source) if tick>before}
            actual=tuple(sorted(receipts.items()))
            self.checks.check(ticks,tuple(tick for tick,_ in actual),'all separated async sends retain exact actual original acceptances')
            self.checks.accepted_burst(actual)
            await self.env.observation.wait('both_complete_prefix_learnings_matured',
                lambda checker:healthy() and not learning_inflight(checker.model.sources.tage))
            self.checks.pending()
        finally:
            for handle in handles:
                if not handle.done() and handle.accepted_event is None:handle.cancel()
