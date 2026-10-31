"""Separate logical histories retain learning through stale migrated feedback."""
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.neighbor_migration import prepare_neighbor_migration, NeighborMigrationService
from suites.frontend.bpu.bpu.checker.neighbor_migration import NeighborMigrationChecks
from suites.frontend.bpu.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS, OUTCOMES


async def check_neighbor_migration(agent, coverage):
    async with direction_program(agent, PC) as env:
        checks = NeighborMigrationChecks(env.checker, coverage)
        await prepare_neighbor_migration(env, checks)
        async with NeighborMigrationService(env, checks) as service:
            await service.start_stream()
            await service.submit(tuple((s, env.branch_path(OUTCOMES)) for s in checks.requests))
            for name, path in HISTORY_PATHS.items():
                checks.consume('blocked', name, await service.query(PC, via=path))
            await service.release()
            for name, path in HISTORY_PATHS.items():
                checks.consume('serviced', name, await env.capture_via(PC, path))
            checks.finish()
