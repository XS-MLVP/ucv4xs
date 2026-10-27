"""A semantic loop outcome owns recovery; younger speculation is not its seed."""
from bpuverify.bpu.env.loop_iteration import loop_iteration_program, final_iteration_program


async def check_loop_iteration(agent, coverage, program):
    async with loop_iteration_program(agent, coverage) as env:
        await env.prepare()
        original = await env.start_loop(program)
        await env.saturate_younger()
        tick = await env.recover(original, program)
        await env.consume(tick)
        env.common.finish()
        return env.common.proof


async def check_final_loop_iteration(agent, coverage):
    async with final_iteration_program(agent, coverage) as env:
        original = await env.prepare_final_repair()
        consumer = await env.consume_final_repair()
        env.common.finish_final_repair(original, consumer)
        return env.common.proof
