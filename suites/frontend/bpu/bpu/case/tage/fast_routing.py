"""Opposed branch-owned directions distinguish raw and qualified selection."""
from suites.frontend.bpu.bpu.case.definitions import PC, POSITION, LATER_POSITION, EARLIER_TARGET, LATER_TARGET
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.checker.tage.fast_routing import TageRoutingChecker
from suites.frontend.bpu.bpu.env.tage_semantic import TageSemanticEnvironment
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback, BpuTraining


async def check_fast_routing(agent,coverage):
    reference = TageRoutingChecker(coverage,pc=PC,positions=(POSITION,LATER_POSITION),targets=(EARLIER_TARGET,LATER_TARGET))
    async with TageSemanticEnvironment(agent,reference) as env:
        ref = env.reference
        await agent.reset(PC)
        anchor = (await agent.next_transaction(start_pc=PC)).meta.redirect
        await agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=True,sc=False,ittage=False,ras=False,settle=True)
        async def query(positions):
            source = await revisit_from_redirect(agent,PC,anchor)
            ref.raise_failure()
            for position in positions:
                ref.source_expected(source,position)
            return source
        def feedback(source,position,target,taken,*,wrong=False):
            return BpuBatchTraining(PC,source.meta.resolve,(
                BpuBranchFeedback(position,target,1,taken=taken,mispredict=int(wrong)),))
        source = await query(())
        if coverage.discovery=='later-first':
            await agent.train(BpuTraining(PC,LATER_POSITION,LATER_TARGET,source.meta.resolve,branch_type=1))
            source = await query((LATER_POSITION,))
        await agent.train(BpuTraining(PC,POSITION,EARLIER_TARGET,source.meta.resolve,branch_type=1))
        source = await query((POSITION,))
        await env.allocate(source,feedback(source,POSITION,EARLIER_TARGET,0,wrong=True),owner=(2,0))
        source = await query((POSITION,))
        await agent.train_batch_with_prediction_pause(feedback(source,POSITION,EARLIER_TARGET,0))
        source = await query((POSITION,))
        ref.earlier_ready(source)
        if coverage.discovery=='earlier-first':
            await agent.train(BpuTraining(PC,LATER_POSITION,LATER_TARGET,source.meta.resolve,branch_type=1))
        await agent.configure_predictors(tage=False,settle=True)
        for _ in range(2):  # Two resolved NT outcomes change the 2-bit base 2 -> 0.
            source = await query(())
            await agent.train_batch_with_prediction_pause(feedback(source,LATER_POSITION,LATER_TARGET,0))
        await agent.configure_predictors(tage=True,settle=True)
        source = await query((POSITION,LATER_POSITION))
        await env.allocate(source,feedback(source,LATER_POSITION,LATER_TARGET,1,wrong=True),owner=(2,1))
        weak = await query((POSITION,LATER_POSITION))
        ref.consumer(weak,await env.corrections(weak),phase='weak')
        await agent.train_batch_with_prediction_pause(feedback(weak,LATER_POSITION,LATER_TARGET,1,wrong=True))
        strong = await query((POSITION,LATER_POSITION))
        ref.consumer(strong,await env.corrections(strong),phase='strong')
        ref.finish()
