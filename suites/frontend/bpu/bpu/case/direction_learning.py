"""Own history and both tables: weaker long provider yields to short alternate."""
from suites.frontend.bpu.bpu.checker.direction_learning import DirectionLearningChecks
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback


PC,POSITION,TARGET = 0x40000800,4,0x40020800


async def check_direction_learning(agent,coverage):
    async with direction_program(agent,PC) as env:
        checks = DirectionLearningChecks(env.checker,PC,POSITION,TARGET,coverage)
        def outcome(taken,wrong):return BpuBranchFeedback(POSITION,TARGET,1,taken=int(taken),mispredict=int(wrong))
        cold = await env.capture_source(PC)
        checks.accepted(await env.resolve(cold,outcome(True,True)),'main')
        main = await env.capture_source(PC)
        checks.observed(main,'main')
        checks.accepted(await env.allocate(main,outcome(False,True),owner=(2,0)),'short')
        short = await env.capture_source(PC)
        checks.observed(short,'short')
        checks.accepted(await env.resolve(short,outcome(False,False)),'short-strong')
        ready = await env.capture_source(PC)
        checks.observed(ready,'short-strong')
        checks.accepted(await env.allocate(ready,outcome(True,True),owner=(3,0)),'promotion')
        promoted = await env.capture_source(PC)
        checks.observed(promoted,'promotion')
        await env.enable_tage(False)
        checks.accepted(await env.resolve(promoted,outcome(True,True)),'base')
        await env.enable_tage(True)
        opposing = await env.capture_source(PC)
        checks.observed(opposing,'base')
        checks.accepted(await env.resolve(opposing,outcome(True,True)),'strong')
        strong = await env.capture_source(PC)
        checks.observed(strong,'strong')
        checks.finish()
