"""Complete one declared semantic program, with no pin or edge mechanics."""
from bpuverify.sc.checker.neutral_boundary import NeutralBoundaryChecks
from bpuverify.sc.env.neutral_boundary import NeutralBoundaryEnv
from bpuverify.sc.model.neutral_boundary import RULES


async def check_neutral_boundary(agent, program, coverage):
    checks = NeutralBoundaryChecks(program)
    try:
        await NeutralBoundaryEnv(agent, program, checks, coverage).run()
        checks.finish()
        for rule in RULES:
            coverage.record('checked', program.label, rule, accepted=len(checks.feedback_records),
                            complete_originals=True, exact_five_family_recovery=True)
        coverage.evidence = dict(checks.summary(), status='PASS')
    except BaseException as error:
        coverage.evidence = dict(checks.summary(), status='FAIL', first_error=str(error))
        raise
