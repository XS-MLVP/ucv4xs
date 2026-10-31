"""Two genuine neutral notifications, bounded program reuse, no slot sweep."""
from suites.frontend.bpu.bpu.env.ras.neutral_gap import ras_neutral_gap_program


async def check_neutral_gap(agent,coverage):
    async with ras_neutral_gap_program(agent,coverage) as program:
        await program.prepare()
        source=await program.threshold()
        source=await program.reclaim(source)
        await program.reuse(source)

