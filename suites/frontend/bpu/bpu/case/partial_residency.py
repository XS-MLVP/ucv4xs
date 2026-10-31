"""Resident learning and absent-key reinstallation have distinct obligations."""
from suites.frontend.bpu.bpu.checker.partial_residency import PartialResidencyChecks
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.partial_residency import prepare_partial_residency, PartialResidencyService
from suites.frontend.bpu.bpu.model.tage.partial_residency import PC, PATHS


async def check_partial_residency(agent, program, coverage):
    async with direction_program(agent, PC) as env:
        checks = PartialResidencyChecks(env.checker, coverage, program)
        await prepare_partial_residency(env, checks)
        async with PartialResidencyService(env, checks) as service:
            for ordinal in range(len(program.stages)):
                checks.begin_stage(ordinal)
                await service.start_stream()
                await service.submit_stage()
                for name, path in PATHS.items():
                    checks.consume('blocked', name, await service.query(PC, via=path))
                await service.release()
                for name, path in PATHS.items():
                    checks.consume('serviced', name, await env.capture_via(PC, path))
            checks.finish()
