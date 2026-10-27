"""Branch-program lifetimes, without pin, edge or coroutine-join mechanics."""
from bpuverify.bpu.env.ahead_working_set import ahead_working_set_env


async def check_ahead_working_set(agent, program, coverage):
    async with ahead_working_set_env(agent, program, coverage) as env:
        source = env.source
        for cohort in range(program.cohorts):
            if cohort:
                source = await env.switch(cohort-1, cohort)
            source = await env.prepare(cohort, source)
            await agent.configure_predictors(abtb=True, settle=True)
            await env.lap(cohort, 'warm')
            await env.lap(cohort, 'late')
        if program.cohorts > 1:
            older = program.cohorts-2
            env.checks.freeze_survivors(older)
            source = await env.switch(program.cohorts-1, older)
            await env.prepare(older, source)
            await agent.configure_predictors(abtb=True, settle=True)
            await env.lap(older, 'late-older-survivors')
        env.checks.finish()


async def check_prefix_working_set(agent,program,coverage):
    from bpuverify.bpu.checker.ahead_working_set import PrefixWorkingSetChecks
    from bpuverify.bpu.env.ahead_working_set import PrefixWorkingSetEnv
    checks=None
    try:
        async with ahead_working_set_env(agent,program,coverage,checks_factory=PrefixWorkingSetChecks,
                environment_factory=PrefixWorkingSetEnv) as env:
            checks=env.checks
            await env.prepare_prefixes()
            for index in program.order:
                source=await env.converge(index,(0,3))
                checks.prefix_consumer(source,index,(0,3),'initial-late')
            for phase,counts in (('selected-early',(3,3)),('selected-NT',(0,0)),('restored-early',(3,0))):
                for index in program.selected:
                    await env.establish(index,counts[0]>=2,counts[1]>=2)
                    await env.converge(index,counts)
                for index in program.order:
                    wanted=counts if index in program.selected else (0,3)
                    source=await env.converge(index,wanted)
                    checks.prefix_consumer(source,index,wanted,phase)
        # Include passive scope/PHR cleanup before granting complete credit.
        checks.finish_prefix()
        coverage.evidence=dict(checks.summary(),status='PASS')
    except BaseException as error:
        if checks is not None:coverage.evidence=dict(checks.summary(),status='FAIL',first_error=str(error))
        raise
