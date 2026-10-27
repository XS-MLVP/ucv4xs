"""Distinct old sources overlap; every effect must survive to saturation."""
from bpuverify.bpu.checker.direction_burst import DirectionBurstChecks
from bpuverify.bpu.env.direction_burst import DirectionBurst
from bpuverify.bpu.env.directions import direction_program
from bpuverify.bpu.model.tage.migration import PC


async def check_direction_burst(agent,coverage,original_way):
    async with direction_program(agent,PC) as env:
        checks=DirectionBurstChecks(env.checker,coverage,original_way)
        program=DirectionBurst(env,checks)
        await program.prepare()
        checks.arm(await program.profile())
        async with program.observe():
            await program.replay()
            for name,source in (await program.profile()).items():checks.consumed(name,source)
            checks.finish()
