"""Selected branch outcomes reverse and recover; other identities keep learning."""
from bpuverify.bpu.checker.ahead_correction import AheadCorrectionChecks
from bpuverify.bpu.env.ahead_correction import AheadCorrectionEnv
from bpuverify.bpu.env.ahead_working_set import ahead_working_set_env


async def check_ahead_correction(agent, program, coverage):
    async with ahead_working_set_env(agent, program, coverage, checks_factory=AheadCorrectionChecks,
                                     environment_factory=AheadCorrectionEnv) as env:
        await env.prepare(0, env.source)
        await agent.configure_predictors(abtb=True, settle=True)
        await env.lap(0, 'warm-positive')
        await env.lap(0, 'late-positive')
        for goal, rounds, phase in ((0, 2, 'negative'), (3, 3, 'restored')):
            await agent.configure_predictors(abtb=False, settle=True)
            for ordinal in range(rounds): await env.direction_round(goal, ordinal)
            await agent.configure_predictors(abtb=True, settle=True)
            await env.lap(0, 'warm-'+phase)
            await env.lap(0, 'late-'+phase)
        env.checks.finish()
