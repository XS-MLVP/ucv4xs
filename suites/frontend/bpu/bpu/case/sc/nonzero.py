"""suites.frontend.bpu.bpu.case.sc.nonzero components."""

from suites.frontend.bpu.bpu.coverage.sc.nonzero import save


async def check_nonzero_history(agent, output, case, group):
    """Construct real history and compare it inside the reusable component."""
    from suites.frontend.bpu.bpu.case.sc.nonzero_scenarios import run_nonzero
    if agent._execution is None:
        raise RuntimeError('SC nonzero-history checks require a started BpuAgent')
    trace = await run_nonzero(agent, agent._execution, output, case)
    for sample in trace['samples']:
        group.sample(sample)
    save(group, output)
