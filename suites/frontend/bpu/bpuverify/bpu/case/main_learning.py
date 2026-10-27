"""A real owner's MainBTB direction defeats then agrees with learned MicroBTB."""
from bpuverify.bpu.checker.main_learning import MainLearningChecks
from bpuverify.bpu.env.branch_targets import branch_target_program
from bpuverify.bpu.transaction.types import BpuBranchFeedback


PC,TARGET,POSITION = 0x40000800,0x40020800,5


async def check_owned_main_learning(agent,coverage,*,pc=PC):
    target = pc+(TARGET-PC)
    async with branch_target_program(agent,pc) as env:
        checks = MainLearningChecks(env.checker,pc,target,POSITION,coverage)
        cold = await env.capture_source(pc)
        checks.accepted(await env.resolve(cold,BpuBranchFeedback(POSITION,target,1,taken=1,mispredict=1)),True)
        positive = await env.capture_source(pc)
        checks.observed(positive,2,False)
        checks.accepted(await env.resolve(positive,BpuBranchFeedback(POSITION,target,1,taken=0,mispredict=1)),False)
        negative = await env.capture_source(pc)
        checks.observed(negative,1,True)
        checks.accepted(await env.resolve(negative,BpuBranchFeedback(POSITION,target,1,taken=1,mispredict=1)),True)
        recovered = await env.capture_source(pc)
        checks.observed(recovered,2,False)
        checks.finish()
        env.checker.finish()
        return dict(accepted=env.checker.counts['feedback'],cycles=env.checker.counts['cycles'],
            main_commits=env.checker.model.sources.main.entry_commits)
