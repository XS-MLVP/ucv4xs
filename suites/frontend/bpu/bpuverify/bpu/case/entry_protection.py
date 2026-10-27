"""Original contribution and error, not physical coordinate coverage."""
from bpuverify.bpu.case.early_opposition import exercise_negative_opposition
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.env.entry_protection import Program
from bpuverify.bpu.checker.entry_protection import Checks


async def run(agent,profile,coverage,evidence):
    checks=Checks(coverage,profile)
    try:
        async with early_direction_program(agent,checks.pc,checks,program_type=Program) as env:
            source=await exercise_negative_opposition(env,checks)
            await env.confirmed_reward(source)
            if checks.program.mode=='contradiction': source=await env.contradict(source)
            final=await env.query(source); checks.final_source(final)
            checks.finish_opposition(env.owners)
    finally: evidence.update(checks.snapshot())
