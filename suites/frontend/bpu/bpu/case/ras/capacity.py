"""Capacity fences, old-prefix rollback and new-identity version reuse."""
from suites.frontend.bpu.bpu.env.ras.capacity import ras_reuse_program


async def check_ras_reuse(agent,coverage):
    async with ras_reuse_program(agent,coverage) as program:
        await program.prepare()
        boundary=await program.guarded()
        await program.reuse(boundary)
        program.checks.finish()
