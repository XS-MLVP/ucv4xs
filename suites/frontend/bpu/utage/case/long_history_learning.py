"""Opposed history paths retain their own learning under adjacent feedback."""
from suites.frontend.bpu.utage.env.long_history_learning import long_history_learning_env


async def check_long_history_learning(agent, mode, coverage):
    async with long_history_learning_env(agent,mode,coverage) as env:
        await env.prepare()
        sources = await env.capture(('a','b','a','b','a','b'))
        await env.batch(sources,(0,1,0,1,0,1),'independent-cumulative-learning')
        sources = await env.capture(('a','b','a','b'))
        await env.batch((sources[1],sources[0]),(1,0),'opposed-boundary-holds')
        await env.batch((sources[2],sources[3]),(1,0),'reverse-from-boundaries')
        env.agent.reference.raise_failure()
        env.checks.finish()
