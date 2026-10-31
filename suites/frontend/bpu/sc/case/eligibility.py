"""Learn -> reject ineligible original queries -> consume restored learning."""
from suites.frontend.bpu.sc.env.eligibility import EligibilityEnv


async def check_eligibility(agent,program,coverage):
    env=EligibilityEnv(agent,program,coverage)
    try:
        async with env:
            await env.learn_originals()
            await env.consume_qualification_changes()
            await env.prove_retained_strength()
            env.finish()
    except BaseException as error:
        coverage.evidence=dict(env.checks.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:
        coverage.evidence=dict(env.checks.summary(),status='PASS',
            scope='isolated prototype with existing SC input cut-point; not current production-run evidence')

