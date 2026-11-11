"""Two migrated providers keep opposed learning through blocked/clean service."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.directions import direction_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.dual_migration import prepare_dual_migration
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.dual_migration import DualMigrationService
from suites.frontend.bpu.testbenches.bpu.checker.dual_migration import DualMigrationChecks
from suites.frontend.bpu.testbenches.bpu.model.tage.dual_migration import PC
from suites.frontend.bpu.testbenches.bpu.model.tage.dual_migration import PATHS
from suites.frontend.bpu.testbenches.bpu.model.tage.dual_migration import OUTCOMES


async def check_dual_migration(agent, coverage):
    async with direction_program(agent, PC) as env:
        checks = DualMigrationChecks(env.checker, coverage)
        await prepare_dual_migration(env, checks)
        async with DualMigrationService(env, checks) as service:
            await service.start_stream()
            await service.submit(tuple((s, env.branch_path(OUTCOMES)) for s in checks.sources[:2]))
            for name, path in PATHS.items():
                checks.consume('blocked', name, await service.query(PC, via=path))
            await service.release()
            for name, path in PATHS.items():
                checks.consume('serviced', name, await env.capture_via(PC, path))
            await service.reactivate()
            for name, path in PATHS.items():
                checks.consume('clean', name, await env.capture_via(PC, path))
            checks.finish()
