"""Adjacent returned outcomes retain their own complete learning and consumers."""
from bpuverify.bpu.checker.joint_originals import Checks
from bpuverify.bpu.env.joint_originals import Environment
from bpuverify.bpu.env.statistical_prefix import experiment
from bpuverify.bpu.bundle.joint_originals import joint_originals_binding


async def check_joint_originals(agent,profile,coverage):
    c=Checks(profile,coverage)
    try:
        async with experiment(agent,c,program_type=Environment,binding_factory=joint_originals_binding) as env:
            sources=await env.capture_originals()
            await env.feedback_originals(sources)
            c.expected_provider=c.program.fresh_counter
            for iteration in c.program.iterations:
                fresh=await env.query_iteration(iteration)
                c.provider(fresh,iteration);c.consume(fresh,iteration,'fresh-'+str(iteration))
        coverage.evidence=c.finish_many(fresh)
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
