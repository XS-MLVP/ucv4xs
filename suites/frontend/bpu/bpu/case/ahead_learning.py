"""Normal branch discovery, ahead consumption and corrected destination."""
from suites.frontend.bpu.bpu.checker.ahead_learning import AheadLearningChecks
from suites.frontend.bpu.bpu.env.ahead_learning import ahead_program
from suites.frontend.bpu.bpu.model.ahead_learning import PC,OTHER,EDGES,NEW_TARGET
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback


async def check_ahead_learning(agent,coverage):
    checks=AheadLearningChecks(coverage)
    async with ahead_program(agent,PC,checks) as env:
        for pc,(position,target) in EDGES.items():
            source=await env.capture_source(pc)
            event=await env.resolve(source,BpuBranchFeedback(position,target,3,taken=1,mispredict=1),retire=False)
            checks.accepted(source,event,target)
        original=await env.run_loop(PC,checks,source_pc=OTHER)
        checks.updating(original)
        event=await env.resolve(original,BpuBranchFeedback(EDGES[original.prediction.start_pc][0],NEW_TARGET,3,taken=1,mispredict=1),retire=False)
        checks.accepted(original,event,NEW_TARGET)
        replayed=await env.consume_target(NEW_TARGET)
        checks.final_consumer(replayed)
        checks.fallback(await env.disabled_fallback(replayed,PC))
        checks.finish()
