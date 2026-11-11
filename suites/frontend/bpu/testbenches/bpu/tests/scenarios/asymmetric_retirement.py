"""Independent histories may retire in different logical orders on two owners."""
from suites.frontend.bpu.testbenches.bpu.checker.asymmetric_retirement import AsymmetricRetirementChecks
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.asymmetric_retirement import prepare_asymmetric_retirement
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.asymmetric_retirement import AsymmetricRetirementService
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.directions import direction_program
from suites.frontend.bpu.testbenches.bpu.model.tage.neighbor_migration import PC
from suites.frontend.bpu.testbenches.bpu.model.tage.neighbor_migration import HISTORY_PATHS


async def check_asymmetric_retirement(agent, coverage):
    async with direction_program(agent, PC) as env:
        checks = AsymmetricRetirementChecks(env.checker, coverage)
        await prepare_asymmetric_retirement(env, checks)
        async with AsymmetricRetirementService(env, checks) as service:
            await service.start_stream()
            await service.submit_prelude()
            await service.submit_late_learning()
            for name, path in HISTORY_PATHS.items():
                checks.consume('blocked', name, await service.query(PC, via=path))
            await service.release()
            for name, path in HISTORY_PATHS.items():
                checks.consume('serviced', name, await env.capture_via(PC, path))
            checks.finish()
