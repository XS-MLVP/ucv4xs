"""Old provider feedback must follow the migrated logical branch, not its old way."""
from suites.frontend.bpu.bpu.checker.direction_migration import DirectionMigrationChecks
from suites.frontend.bpu.bpu.env.direction_migration import DirectionMigration
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.model.tage.migration import PC


async def check_direction_migration(agent,coverage,original_way):
    async with direction_program(agent,PC) as env:
        checks=DirectionMigrationChecks(env.checker,coverage,original_way)
        program=DirectionMigration(env,checks)
        await program.prepare()
        checks.arm(await program.profile())
        async with program.observe():
            await program.replay()
            for name,source in (await program.profile()).items():checks.consumed(name,source)
            checks.finish()
