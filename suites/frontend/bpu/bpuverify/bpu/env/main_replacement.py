"""Original prediction sources and adjacent driver submissions, no pin timing."""
from contextlib import asynccontextmanager

from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.main_service import MainProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.main_sources import BranchTargetSources
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback
from bpuverify.mbtb.model.replacement_overlap import PC


@asynccontextmanager
async def replacement_program(agent):
    phr=BpuPhrChecker(scope='original-source MainBTB adjacent replacement')
    async with PipelineObservation(agent,sources=BranchTargetSources()) as observation,agent.observe_phr(phr):
        await agent.reset(PC)
        anchor=await agent.next_transaction(start_pc=PC)
        await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=False,sc=False,
                                        ittage=False,ras=False,settle=True)
        yield MainProgram(agent,observation,anchor,PC)
        phr.summary()


def branch(record,*,taken=True,wrong=False):
    return BpuBranchFeedback(record.position,record.target,1,taken=int(taken),mispredict=int(wrong))


async def adjacent_feedback(env,sources,outcomes,checks):
    transactions=tuple(BpuBatchTraining(source.prediction.start_pc,source.meta.resolve,tuple(branches))
                       for source,branches in zip(sources,outcomes,strict=True))
    for source,transaction in zip(sources,transactions,strict=True):env.checker.plan_feedback(source,transaction)
    before=env.checker.last_tick
    driver_ticks=await env.agent.train_batches(transactions)
    await env.pause()
    accepted=tuple(sorted((tick,resolution) for source in sources
        for tick,resolution in env.checker.resolutions_for_source(source) if tick>before))
    checks.check(driver_ticks,tuple(tick for tick,_ in accepted),'driver accepts equal independent input monitor receipts')
    def expected(tx):
        return tx.pc,tuple((b.position,b.target,b.taken,b.branch_type,b.ras_action,b.mispredict) for b in tx.branches)
    def actual(resolution):
        return resolution.pc,tuple((b.position,b.target,int(b.taken),int(b.kind),int(b.action),int(b.mispredict))
            for b in resolution.branches if b is not None)
    checks.admissions(tuple(tick for tick,_ in accepted),tuple(actual(r) for _,r in accepted),
                      tuple(expected(tx) for tx in transactions))
