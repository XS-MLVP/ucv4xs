"""One weak owner, two real adjacent positive updates, then public proof."""
from suites.frontend.bpu.bpu.checker.micro_forwarding import MicroForwardingChecks
from suites.frontend.bpu.bpu.env.micro import micro_program
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


PC,TARGET,POSITION = 0x40000800,0x40020800,5


async def check_micro_forwarding(agent,coverage):
    async with micro_program(agent,PC) as env:
        checks = MicroForwardingChecks(env.checker,PC,TARGET,POSITION,coverage)
        source = await env.capture(PC,lambda source:checks.source(source,hit=False))
        await env.train(PC,source,TARGET,POSITION)
        for _ in range(2):
            await env.capture(PC,lambda source:checks.source(source,hit=True,origin=True))
        checks.require_weak()
        feedback = tuple(BpuBatchTraining(PC,source.meta.resolve,(
            BpuBranchFeedback(POSITION,TARGET,2,taken=1,mispredict=1),)) for source in checks.origins)
        ticks = await env.train_burst(feedback)
        checks.burst_delivered(ticks)
        for hit in (True,True,True,False):
            await env.capture(PC,lambda source:checks.source(source,hit=hit,probe=True))
        checks.finish()
        return dict(sources=len(checks.origins),probes=checks.probes,accepted=tuple(tick for tick,_ in checks.accepted))
