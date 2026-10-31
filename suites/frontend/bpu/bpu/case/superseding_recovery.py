"""Run one complete surviving-prefix requirement, then grant checked credit."""
from suites.frontend.bpu.bpu.env.superseding_recovery import superseding_recovery_env
from suites.frontend.bpu.bpu.model.superseding_recovery import RULES


async def check_superseding_recovery(agent, program, coverage):
    checks = None
    try:
        async with superseding_recovery_env(agent, program, coverage) as env:
            checks = env.common
            await env.run_pair(program)
        checks.finish_pair()
        for rule in RULES:
            coverage.record('checked', program.profile, rule, complete_original_lifetimes=True)
        coverage.evidence = dict(checks.summary(), status='PASS')
    except BaseException as error:
        coverage.evidence = dict({} if checks is None else checks.summary(), status='FAIL', first_error=str(error))
        raise
