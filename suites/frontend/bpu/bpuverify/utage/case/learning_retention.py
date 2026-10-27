"""Learning remains valid after unrelated learning removes its recent copies."""
from bpuverify.utage.env.learning_retention import learning_retention_env


async def check_learning_retention(agent, program, coverage):
    async with learning_retention_env(agent, program, coverage) as lifetime:
        await lifetime.prepare()
        await lifetime.learn(lifetime.retained, 'retained-learning')
        await lifetime.consume(lifetime.retained, 'immediate-bypass-consumers')
        await lifetime.learn(lifetime.turnover, 'unrelated-learning')
        lifetime.confirm_turnover()
        await lifetime.consume(lifetime.retained, 'fresh-after-turnover-consumers')
        lifetime.finish()
