"""A shorter-history alternate must beat both weak provider and opposite base."""
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.checker.assertions import revisit_from_redirect, mbtb_counter_for_position
from bpuverify.bpu.checker.tage.alternate import TageAlternateChecker
from bpuverify.bpu.env.tage_semantic import TageSemanticEnvironment
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback, BpuTraining


POSITIONS = (8,10)
TARGETS = (PC+0x180,PC+0x300)


async def check_alternate(agent,coverage):
    checker = TageAlternateChecker(coverage,pc=PC,positions=POSITIONS,targets=TARGETS)
    async with TageSemanticEnvironment(agent,checker) as env:
        ref = env.reference
        await agent.reset(PC)
        anchor = (await agent.next_transaction(start_pc=PC)).meta.redirect
        await agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=False,sc=False,ittage=False,ras=False,settle=True)
        async def query(*,checked=True):
            source = await revisit_from_redirect(agent,PC,anchor)
            ref.raise_failure()
            if checked:
                for position in POSITIONS:
                    ref.source_expected(source,position)
            return source
        def feedback(source,position,taken,wrong=False):
            return BpuBatchTraining(PC,source.meta.resolve,(BpuBranchFeedback(position,TARGETS[POSITIONS.index(position)],
                1,taken=taken,mispredict=int(wrong)),))
        source = await query(checked=False)
        for position,target in zip(POSITIONS,TARGETS,strict=True):
            await agent.train(BpuTraining(PC,position,target,source.meta.resolve,branch_type=1))
            source = await query(checked=False)
        for index in range(2):  # Two NT outcomes reduce the sentinel base 2 -> 0.
            await agent.train_batch_with_prediction_pause(feedback(source,POSITIONS[0],0,wrong=index==0))
            source = await query(checked=False)
        assert mbtb_counter_for_position(source,POSITIONS[0]) == 0
        await agent.configure_predictors(tage=True,settle=True)
        source = await query()
        await env.allocate(source,feedback(source,POSITIONS[1],0,wrong=True),owner=(2,0))
        source = await query()
        for _ in range(2):  # Genuine NT learning strengthens the T2 counter 3 -> 1.
            await agent.train_batch_with_prediction_pause(feedback(source,POSITIONS[1],0))
            source = await query()
        lower = ref.source_expected(source,POSITIONS[1])
        assert (lower['providerTableIdx'],lower['providerTakenCtr_value'],lower['hasAlt']) == (2,1,0)
        await env.allocate(source,feedback(source,POSITIONS[1],1,wrong=True),owner=(3,0))
        source = await query()
        promoted = ref.source_expected(source,POSITIONS[1])
        assert (promoted['providerTableIdx'],promoted['providerTakenCtr_value'],promoted['hasAlt']) == (3,4,1)
        await agent.configure_predictors(tage=False,settle=True)
        for index in range(2):  # Oppose the retained NT alternate with a taken base.
            source = await query(checked=False)
            await agent.train_batch_with_prediction_pause(feedback(source,POSITIONS[1],1,wrong=index==0))
        await agent.configure_predictors(tage=True,settle=True)
        weak = await query()
        assert mbtb_counter_for_position(weak,POSITIONS[1]) == 3
        meta = ref.source_expected(weak,POSITIONS[1])
        assert (meta['hasAlt'],meta['altOrBasePred'],meta['altConf'],meta['useProvider']) == (1,0,1,0)
        assert ref.consumer(weak,await env.corrections(weak)) == 'weak'
        await agent.train_batch_with_prediction_pause(feedback(weak,POSITIONS[1],1,wrong=True))
        strong = await query()
        meta = ref.source_expected(strong,POSITIONS[1])
        assert (meta['providerTableIdx'],meta['providerWayIdx'],meta['providerTakenCtr_value'],meta['hasAlt'],meta['useProvider']) == (3,0,5,1,1)
        assert ref.consumer(strong,await env.corrections(strong)) == 'strong'
        assert mbtb_counter_for_position(strong,POSITIONS[0]) == 0
        ref.finish()
