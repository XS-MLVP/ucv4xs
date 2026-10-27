"""Six independent maintenance/learning events, not a bank/set traversal."""
from bpuverify.utage.checker.aging_learning import AgingLearningChecks
from bpuverify.utage.env.aging_learning import AgingLearningEnv


async def check_aging_learning(agent, program, coverage):
    await agent.reset()
    checks = AgingLearningChecks(program, coverage)
    async with agent.observe_useful(checks):
        env = AgingLearningEnv(agent, checks)
        for learning in program.preparation:
            await env.learn(learning, phase='prepare independent resident')
        target = program.target_learning
        target_source = await env.source(target.source)
        for previous in range(program.ordinary_failures):
            await env.learn(program.failed_source(previous), phase='qualifying allocation failure')
        threshold = program.failed_source(program.ordinary_failures)
        failure_source = await env.source(threshold.source)
        checks.arm()
        await env.send_many(((threshold, failure_source, 'threshold-failure'),
                             (target, target_source, 'overlap-target')))
        for expected in program.consumers:
            await env.consumer(expected)
        agent.reference.raise_failure()
        checks.finish()
