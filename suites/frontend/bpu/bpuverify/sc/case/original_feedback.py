"""Semantic lifetime intent; all driving and observation live in env."""
from bpuverify.sc.env.original_feedback import FeedbackEnv


async def check_ignored_original_feedback(agent,program,coverage):
    env=FeedbackEnv(agent,program,coverage)
    try:
        async with env:
            await env.learn_originals()
            await env.consume_qualification_changes()
            await env.ignore_original_outcomes()
            await env.prove_retained_strength()
            env.finish()
    except BaseException as error:
        coverage.evidence=dict(env.checks.summary(),status='FAIL',first_error=str(error),first_error_type=type(error).__name__)
        raise
    else:
        coverage.evidence=dict(env.checks.summary(),status='PASS',scope='isolated original-feedback cutpoint, not production evidence')
