"""New learning reuses only released capacity; old pending identities survive."""
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.neighbor_migration import prepare_neighbor_migration
from suites.frontend.bpu.bpu.env.partial_reuse import PartialReuseService
from suites.frontend.bpu.bpu.checker.partial_reuse import PartialReuseChecks
from suites.frontend.bpu.bpu.model.tage.partial_reuse import PC, HISTORY_PATHS, OUTCOMES, INITIAL_INPUTS


async def check_partial_reuse(agent, coverage):
    async with direction_program(agent, PC) as env:
        checks = PartialReuseChecks(env.checker, coverage)
        await prepare_neighbor_migration(env, checks)
        async with PartialReuseService(env, checks) as service:
            await service.start_stream()
            await service.submit(tuple((s, env.branch_path(OUTCOMES)) for s in checks.requests[:INITIAL_INPUTS]))
            await service.release_one_pair()
            await service.submit(tuple((s, env.branch_path(OUTCOMES)) for s in checks.requests[INITIAL_INPUTS:]))
            for name, path in HISTORY_PATHS.items():
                checks.consume('blocked', name, await service.query(PC, via=path))
            await service.release()
            for name, path in HISTORY_PATHS.items():
                checks.consume('serviced', name, await env.capture_via(PC, path))
            checks.finish()
