"""bpuverify.bpu.case.sc.role components."""

from bpuverify.common.coverage.exports import write_functional_coverage

from bpuverify.common.env.artifacts import output_path
from toffee import CoverageDatabase
from bpuverify.bpu.case.sc.role_scenarios import run_depth
from bpuverify.bpu.coverage.sc.role import group
from bpuverify.bpu.coverage.sc.role import qualified_samples


async def check_four_key_roles(agent, execution, output, case, groups):
    trace = await run_depth(agent, execution, output, case)
    for group, samples in zip(groups, qualified_samples(trace), strict=True):
        for sample in samples:
            group.sample(sample)
    write_functional_coverage(CoverageDatabase(groups), output_path(output / 'functional-coverage-sc-four-key-provider-roles.json'))


async def check_provider_roles(agent, output, case, groups):
    """Hide Execution and all monitor/coverage mechanics from testcase intent."""
    if agent._execution is None:
        raise RuntimeError('SC provider-role checks require a started BpuAgent')
    await check_four_key_roles(agent, agent._execution, output, case, groups)
