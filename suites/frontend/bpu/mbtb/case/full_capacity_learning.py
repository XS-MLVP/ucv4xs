"""Branch-program intent; no signal scheduling or reference resynchronization."""
from suites.frontend.bpu.mbtb.env.full_capacity_learning import FullCapacityEnv


async def check_full_capacity_learning(agent, mode, order, coverage, *, position_relation='same-position'):
    env = FullCapacityEnv(agent, mode, order, coverage, position_relation=position_relation)
    try:
        await env.prepare()
        await env.learn_pair()
        await env.compete()
        env.checks.finish()
        agent.reference.raise_failure()
    except Exception as error:
        env.annotate_failure(error)
        raise
