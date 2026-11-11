"""Original history, younger speculation, legal recovery and fresh consumer."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.common_query import common_query_program
from suites.frontend.bpu.testbenches.bpu.model.common_query import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.loop_iteration import PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.loop_iteration import IterationProgram
from suites.frontend.bpu.testbenches.bpu.model.loop_iteration import FORWARD
from suites.frontend.bpu.testbenches.bpu.model.selection import Branch
from suites.frontend.bpu.testbenches.bpu.model.selection import Kind


async def run(agent, profile, coverage):
    if profile not in PROFILES:
        raise ValueError('declared query-history program required')
    final = profile == 'final-direction-repair'
    mixed = profile == 'two-condition-prefix-direct-recovery'
    async with common_query_program(agent, final=final, mixed=mixed, coverage=coverage) as env:
        if final:
            original = await env.prepare_final_repair()
            consumer = await env.consume_final_repair()
            env.common.finish_final_repair(original, consumer)
        else:
            program = (IterationProgram(profile, Branch(5, FORWARD, Kind.DIRECT)) if mixed else
                       next(program for program in PROGRAMS if program.name == profile))
            await env.prepare()
            original = await env.start_loop(program)
            await env.saturate_younger()
            tick = await env.recover(original, program)
            await env.consume(tick)
            env.common.finish()
        return env.common.finish_query()
