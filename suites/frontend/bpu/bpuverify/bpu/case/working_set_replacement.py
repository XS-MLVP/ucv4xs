"""Existing natural-program operations; no raw signal or clock scheduling."""
from bpuverify.bpu.env.ahead_working_set import ahead_working_set_env
from bpuverify.bpu.checker.working_set_replacement import Checks


async def check_ahead_identity_replacement(agent, program, coverage):
    async with ahead_working_set_env(agent, program, coverage, checks_factory=Checks) as env:
        source = env.source
        for cohort in range(program.cohorts):
            if cohort:
                source = await env.switch(cohort - 1, cohort)
            source = await env.prepare(cohort, source)
            await agent.configure_predictors(abtb=True, settle=True)
            await env.lap(cohort, 'warm')
            await env.lap(cohort, 'late')
        older = program.cohorts - 2
        env.checks.freeze_survivors(older)
        source = await env.switch(program.cohorts - 1, older)
        await env.prepare(older, source)
        await agent.configure_predictors(abtb=True, settle=True)
        await env.lap(older, 'late-older-survivors')
        env.checks.finish()
