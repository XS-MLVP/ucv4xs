"""Independent semantic scenarios, not a chain across physical coordinates."""
from suites.frontend.bpu.utage.env.usefulness_events import usefulness_env
from suites.frontend.bpu.utage.model.usefulness_events import HISTORY, NEIGHBOR_HISTORY


async def check_usefulness_event(agent, program, coverage):
    async with usefulness_env(agent, program, coverage) as env:
        await env.seed(NEIGHBOR_HISTORY)
        original = await env.seed(HISTORY, credit=program.rule == 'initial-protection')
        env.useful(program.initial.useful)
        if program.rule == 'initial-protection':
            await env.consumers(program.initial)
            env.finish()
            return
        count, taken = program.preparation
        if count:
            await env.feedback(original, taken, count=count, phase='independently prepare event prestate')
        env.useful(program.prepared.useful)
        # An old wrong-prediction source is necessary to test zero hold after
        # the direction counter has crossed; every other event captures fresh.
        source = original if program.rule == 'lower-hold' else await env.read(
            env.source_history, program.base, expected=program.source)
        await env.feedback(source, program.actual, count=2, phase=program.rule,
                           mode=program.mode, credit=True)
        env.useful(program.expected[-1].useful)
        await env.consumers(program.expected[-1])
        env.finish()
