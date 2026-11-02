"""Autonomous BPU programs checked by owned tokens and learned MicroBTB state."""
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect, BpuBatchTraining, BpuBranchFeedback
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker


PC = 0x40000800


async def check_stream(agent, coverage=None):
    phr = BpuPhrChecker(scope='autonomous held request/recovery public projection',record_limit=8)
    async with PipelineObservation(agent,coverage) as observation,agent.observe_phr(phr) as history:
        await agent.reset(PC)
        source = await agent.next_transaction(start_pc=PC)
        await agent.configure_predictors(ubtb=False, abtb=False, mbtb=False,
            tage=False, sc=False, ittage=False, ras=False, settle=True)
        checker = observation.checker
        checker.phase = 'stall'
        before = checker.counts['metadata-without-prediction-acceptance']
        await agent.set_ready(prediction=False, meta=True)
        await observation.wait('metadata_is_valid_only', lambda c:c.counts['metadata-without-prediction-acceptance']>before)
        await observation.wait('older_tokens_drained', lambda c:c.last_cycle is not None
                               and c.last_cycle.tokens[0] is not None and c.last_cycle.tokens[1:] == (None,None))
        checker.phase = 'redirect'
        request=BpuRedirect(PC+0x7F9, source.meta.redirect, cfi_pc=PC+4, taken=1, branch_type=2)
        checker.plan_redirect(source,request)
        await agent.redirect(request)
        await observation.wait('held_redirect_issued', lambda c:c.counts['redirect-held']>0)
        checker.phase = 'reopen'
        before = checker.counts['metadata']
        reopened = await agent.set_ready(prediction=True, meta=True)
        await observation.wait('recovered_tokens_retired', lambda c:c.counts['metadata']>=before+2)
        # No metadata ready pin exists. Older accepted S3 work must retire even
        # with prediction acceptance stopped; it was compared above, not by a
        # fabricated metadata-ready-low scenario.
        resumed = await agent.next_transaction(after_tick=reopened)
        checker.raise_failure()
        assert checker.last_events.metadata_ready and resumed.meta_tick == resumed.prediction_tick + 4
        assert resumed.prediction.target is None and resumed.meta.perf is None
        await agent.set_ready(prediction=False, meta=True)
        await history.drain()
        if coverage is not None:
            coverage.finish()
        return checker


async def check_micro_repair(agent, coverage=None):
    phr = BpuPhrChecker(scope='autonomous micro middle-repair public projection',record_limit=8)
    async with PipelineObservation(agent,coverage) as observation,agent.observe_phr(phr) as history:
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        await agent.configure_predictors(ubtb=True, abtb=False, mbtb=False,
            tage=False, sc=False, ittage=False, ras=False, settle=True)
        checker = observation.checker
        transaction=BpuBatchTraining(PC,anchor.meta.resolve,(BpuBranchFeedback(4,PC+0x200,2,mispredict=1),))
        checker.plan_feedback(anchor,transaction)
        await agent.train_batch(transaction)
        await observation.wait('first_micro_resident', lambda c:c.model.sources.resident(PC))
        request=BpuRedirect(PC+0x200, anchor.meta.redirect, cfi_pc=PC+4)
        checker.plan_redirect(anchor,request)
        tick = await agent.redirect(request)
        second = await agent.next_transaction(start_pc=PC+0x200, after_tick=tick)
        transaction=BpuBatchTraining(PC+0x200,second.meta.resolve,(BpuBranchFeedback(6,PC+0xE000,2,mispredict=1),))
        checker.plan_feedback(second,transaction)
        await agent.train_batch(transaction)
        await observation.wait('second_micro_resident', lambda c:c.model.sources.resident(PC+0x200))
        checker = observation.checker
        checker.phase = 'repair'
        before = checker.counts['middle-repair']
        request=BpuRedirect(PC, anchor.meta.redirect, cfi_pc=PC+4)
        checker.plan_redirect(anchor,request)
        await agent.redirect(request)
        await observation.wait('owned_middle_repair', lambda c:c.counts['middle-repair']>before)
        await observation.wait('corrected_source_retired', lambda c:c.last_cycle is not None
             and c.last_cycle.metadata is not None and c.last_cycle.metadata.pc == PC
             and c.last_cycle.metadata.middle_corrected)
        await agent.set_ready(prediction=False, meta=True)
        await history.drain()
        if coverage is not None:
            coverage.finish()
        return checker
