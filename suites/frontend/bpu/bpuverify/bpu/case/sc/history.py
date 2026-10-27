"""bpuverify.bpu.case.sc.history components."""

from bpuverify.bpu.coverage.sc.history import save


async def check_history_training(agent, output, case, group):
    """Credit bins only after full reset/state/source/public checks pass."""
    from bpuverify.bpu.case.sc.history_training import check_history_training as run
    if agent._execution is None:
        raise RuntimeError('SC history checks require a started BpuAgent')
    trace = await run(agent, agent._execution, output, case)
    for sample in trace['samples']:
        group.sample(sample)
    save(group, output)
