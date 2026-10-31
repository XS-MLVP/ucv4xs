"""Six semantic consumers bracket an actual old/new learning collision."""
from suites.frontend.bpu.bpu.bundle.shared_saturation import binding
from suites.frontend.bpu.bpu.checker.service_relearning import Checks
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.direction_service import prepare_service_stream
from suites.frontend.bpu.bpu.env.service_relearning import Service
from suites.frontend.bpu.bpu.model.tage.forwarding import PC, resolved_path
from suites.frontend.bpu.bpu.model.tage.service import VIA_PC


async def run(agent, program, coverage, evidence):
    checks = None
    try:
        async with direction_program(agent, PC) as env:
            checks = Checks(env.checker, coverage, program)
            await env.prepare_direction_pair(checks.prepared)
            await env.prepare_second_history(checks.prepared)
            sources = []
            for history in program.service_program.feedback_order:
                sources.append(await env.capture_source(PC) if history == 0 else await env.capture_via(PC, VIA_PC))
            await prepare_service_stream(env)
            checks.arm(tuple(sources))
            async with Service(env, checks, binding_factory=binding) as service:
                await service.start_stream()
                await service.submit(tuple((s, env.branch_path(resolved_path())) for s in sources[:2]))
                checks.consume('old', 0, await service.query(PC))
                checks.consume('old', 1, await service.query(PC, via=VIA_PC))
                await service.overlap_learning(sources[2], env.branch_path(program.late_path))
                checks.consume('mixed', 0, await service.query(PC))
                checks.consume('mixed', 1, await service.query(PC, via=VIA_PC))
                await service.release_remaining()
                checks.consume('final', 0, await env.capture_source(PC))
                checks.consume('final', 1, await env.capture_via(PC, VIA_PC))
                checks.finish()
    finally:
        if checks is not None: evidence.update(checks.snapshot())
