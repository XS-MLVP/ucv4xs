"""Autonomous BPU programs checked by owned tokens and learned MicroBTB state."""
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.transaction.types import BpuRedirect, BpuTraining


PC = 0x40000800


async def check_stream(agent, coverage=None):
    async with PipelineObservation(agent,coverage) as observation:
        await agent.reset(PC)
        source = await agent.next_transaction(start_pc=PC)
        await agent.configure_predictors(ubtb=False, abtb=False, mbtb=False,
            tage=False, sc=False, ittage=False, ras=False, settle=True)
        checker = observation.checker
        checker.phase = 'stall'
        before = checker.counts['metadata-unready']
        await agent.set_ready(prediction=False, meta=False)
        await observation.wait('metadata_is_valid_only', lambda c:c.counts['metadata-unready']>before)
        await observation.wait('older_tokens_drained', lambda c:c.last_cycle is not None
                               and c.last_cycle.tokens[0] is not None and c.last_cycle.tokens[1:] == (None,None))
        checker.phase = 'redirect'
        await agent.redirect(BpuRedirect(PC+0x7F9, source.meta.redirect, cfi_pc=PC+4, taken=1, branch_type=2))
        await observation.wait('held_redirect_issued', lambda c:c.counts['redirect-held']>0)
        checker.phase = 'reopen'
        reopened = await agent.set_ready(prediction=True, meta=False)
        before = checker.counts['metadata-unready']
        await observation.wait('recovered_tokens_retired', lambda c:c.counts['metadata-unready']>=before+2)
        # The production receiver must collect this valid-only S3 beat even
        # while the physical metadata ready pin stays low; no alternate stream
        # or fuzzy source matching is used to repair a lost receipt.
        resumed = await agent.next_transaction(after_tick=reopened)
        checker.raise_failure()
        assert not checker.last_events.metadata_ready and resumed.meta_tick == resumed.prediction_tick + 4
        await agent.set_ready(prediction=True, meta=True)
        if coverage is not None:
            coverage.finish()
        return checker


async def check_micro_repair(agent, coverage=None):
    async with PipelineObservation(agent,coverage) as observation:
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        await agent.configure_predictors(ubtb=True, abtb=False, mbtb=False,
            tage=False, sc=False, ittage=False, ras=False, settle=True)
        await agent.train(BpuTraining(PC, 4, PC+0x200, anchor.meta.resolve, branch_type=2))
        await observation.wait('first_micro_resident', lambda c:c.model.sources.resident(PC))
        tick = await agent.redirect(BpuRedirect(PC+0x200, anchor.meta.redirect, cfi_pc=PC+4))
        second = await agent.next_transaction(start_pc=PC+0x200, after_tick=tick)
        await agent.train(BpuTraining(PC+0x200, 6, PC+0xE000, second.meta.resolve, branch_type=2))
        await observation.wait('second_micro_resident', lambda c:c.model.sources.resident(PC+0x200))
        checker = observation.checker
        checker.phase = 'repair'
        before = checker.counts['middle-repair']
        await agent.redirect(BpuRedirect(PC, anchor.meta.redirect, cfi_pc=PC+4))
        await observation.wait('owned_middle_repair', lambda c:c.counts['middle-repair']>before)
        await observation.wait('corrected_source_retired', lambda c:c.last_cycle is not None
            and c.last_cycle.metadata is not None and c.last_cycle.metadata.pc == PC
            and c.last_cycle.metadata.middle_corrected)
        if coverage is not None:
            coverage.finish()
        return checker
