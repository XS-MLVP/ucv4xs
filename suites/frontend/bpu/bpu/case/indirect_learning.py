"""One learned indirect target must defeat Main until zero-conf retarget completes."""
from suites.frontend.bpu.bpu.checker.indirect_learning import IndirectLearningChecks
from suites.frontend.bpu.bpu.env.indirect_learning import indirect_program
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback

PC=0x40000800
POSITION=4
INITIAL=PC+0x400
TARGET=PC+0x600


async def check_indirect_learning(agent,coverage):
    async with indirect_program(agent,PC) as env:
        checks=IndirectLearningChecks(env.checker,coverage,PC,POSITION,INITIAL,TARGET)
        source=await env.cold_source(PC,table=4);checks.cold(source)
        for resolved,confidence,learned,repair in ((INITIAL,2,INITIAL,False),
                (TARGET,1,INITIAL,True),(TARGET,0,INITIAL,True),(TARGET,0,TARGET,False)):
            event=await env.resolve(source,BpuBranchFeedback(POSITION,resolved,3,taken=1,mispredict=1))
            checks.accepted_feedback(source,event,resolved)
            source=await env.capture_source(PC)
            checks.consumed(source,confidence=confidence,main=resolved,target=learned,repair=repair)
        checks.finish()
