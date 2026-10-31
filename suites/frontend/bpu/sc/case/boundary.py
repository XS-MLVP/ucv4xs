"""Delayed real-source learning, boundary holds and fresh reverse consumers."""
from suites.frontend.bpu.sc.checker.boundary import ScBoundaryChecks
from suites.frontend.bpu.sc.model.boundary import ScBoundaryProgram, expected_feedback, observed_feedback
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel


async def check_weight_boundary(agent, coverage, *, direction):
    program = ScBoundaryProgram(direction)
    checks = ScBoundaryChecks(program)
    thresholds = ScThresholdModel.for_default()
    boundary = 'upper' if direction else 'lower'
    await agent.reset()
    await agent.check_thresholds(thresholds.values)
    cold_expected = program.expected(0, thresholds.values)
    # Submit distinct occurrences before any feedback. The framework owns
    # launch/response concurrency and association, not asyncio in a test case.
    pending = [agent.submit_predict_branches(program.pc, program.layout)
               for _ in range(program.source_count)]
    await agent.drain_predictions()
    sources = [checks.source(transfer, await transfer, cold_expected, state='real cold source')
               for transfer in pending]
    last_cold_response = max(checks.sources[source]['completed'] for source in sources)
    branch_count = len(agent.ports.training.bits.branches)
    fold_count = len(agent.ports.training.bits.path_history)

    async def read(weight):
        transfer = agent.submit_predict_branches(program.pc, program.layout)
        prediction = await transfer
        expected = program.expected(weight, thresholds.values)
        checks.prediction(expected, prediction, state=dict(weight=weight, thresholds=thresholds.values))
        await agent.check_thresholds(thresholds.values)
        return transfer, prediction, expected

    async with agent.observe_feedback() as frames:
        async def send(source, *, reverse=False):
            actual, expected = checks.feedback(source, reverse=reverse)
            update = thresholds.apply(expected)
            checks.check((0,), update.qualifying_slots, request='each original source genuinely learns')
            start = len(frames)
            intended = expected_feedback(expected, branch_count=branch_count, fold_count=fold_count)
            await agent.train_batch(actual)
            observed = frames[start:]
            checks.check((intended,), tuple(observed_feedback(frame.value) for frame in observed),
                         request=dict(source_id=source, expected_feedback=expected))
            checks.accepted(source, observed[0].event.tick)
            checks.check(True, last_cold_response < observed[0].event.tick,
                         request='all cold source responses precede learning')

        for step, source in enumerate(sources, 1):
            await send(source)
            if step in (program.approach_steps, program.source_count):
                phase = 'approach' if step == program.approach_steps else 'hold'
                coverage.record('reached', f'{boundary}-{phase}', accepted=step,
                                endpoint=program.endpoint, distinct_sources=len(sources))
            current = await read(program.weight(step))

        for step in range(1, program.reverse_steps + 1):
            transfer, prediction, expected = current
            source = checks.source(transfer, prediction, expected,
                                   state=dict(phase='fresh reverse', step=step))
            await send(source, reverse=True)
            if step == 1:
                coverage.record('reached', f'{boundary}-recover', original_endpoint=program.endpoint)
            current = await read(program.weight(program.source_count, reverse=step))

        checks.finish()
        for phase in ('approach', 'hold', 'recover'):
            coverage.record('checked', f'{boundary}-{phase}', distinct_cold_sources=len(sources),
                reverse_steps=program.reverse_steps, full_family_consumers=True, snapshots_unchanged=True)
