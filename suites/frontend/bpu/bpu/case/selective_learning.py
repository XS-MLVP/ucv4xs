"""Semantic program only: public originals, parallel learning, checked consumers."""
from suites.frontend.bpu.bpu.bundle.shared_saturation import binding
from suites.frontend.bpu.bpu.checker.selective_learning import Checks
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.direction_service import prepare_service_stream
from suites.frontend.bpu.bpu.env.selective_learning import LearningService, capture, prepare
from suites.frontend.bpu.bpu.model.tage.forwarding import PC


async def check_selective_learning(agent, program, coverage, evidence):
    async with direction_program(agent, PC) as environment:
        checks = Checks(environment.checker, coverage, program)
        try:
            await prepare(environment, checks)
            originals = tuple([await capture(environment, program.paths[h]) for h in program.feedback_order])
            await prepare_service_stream(environment)
            checks.arm(originals)
            async with LearningService(environment, checks, binding_factory=binding) as service:
                await service.start_stream()
                await service.send_indices(program.first_batch)
                for h, path in enumerate(program.paths):
                    checks.consume('old-first', h, await service.query(PC, via=path), program.initial)
                await service.release()
                for h, path in enumerate(program.paths):
                    checks.consume('new-first', h, await capture(environment, path), program.counters(h, checks.counts[h]))
                if program.boundary == 'already-serviced':
                    await service.start_stream()
                    await service.send_indices((len(originals)-1,))
                    for h, path in enumerate(program.paths):
                        checks.consume('old-held', h, await service.query(PC, via=path), program.counters(h, checks.counts[h]))
                    await service.release()
                    for h, path in enumerate(program.paths):
                        checks.consume('new-held', h, await capture(environment, path), program.counters(h, checks.counts[h]))
            source = await capture(environment, program.paths[program.target])
            reverse = await environment.resolve(source, *environment.branch_path(program.reverse_outcome))
            changed = await capture(environment, program.paths[program.target])
            restore = await environment.resolve(changed, *environment.branch_path(program.restore_outcome))
            restored = await capture(environment, program.paths[program.target])
            preserved = tuple([await capture(environment, path) for path in program.paths])
            checks.recovered(((source, reverse, changed), (changed, restore, restored)), preserved)
            checks.finish()
            for item in (source, changed, restored, *preserved): environment.checker.retire_source(item.meta_tick)
        finally:
            evidence.update(checks.snapshot())
