"""Semantic lifetime intent; all driving and observation live in env."""
from bpuverify.sc.env.original_enable import EnableEnv


async def check_enable_lifetime(agent,program,coverage):
    env=EnableEnv(agent,program,coverage)
    try:
        async with env:
            await env.learn_originals()
            await env.consume_qualification_changes()
            await env.disable_old_outcomes_and_reopen()
            await env.prove_retained_strength()
            env.finish()
    except BaseException as error:
        coverage.evidence=dict(env.checks.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:coverage.evidence=dict(env.checks.summary(),status='PASS',scope='isolated SC original-source enable lifetime, not production')
