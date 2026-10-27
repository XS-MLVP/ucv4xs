"""Original loop experience survives younger predictions and feedback arrival."""
from bpuverify.bpu.checker.sc_loop_experience import Checks
from bpuverify.bpu.env.sc_loop_experience import Environment
from bpuverify.bpu.env.statistical_prefix import experiment


async def check_loop_experience(agent,profile,coverage):
    c=Checks(profile,coverage)
    try:
        async with experiment(agent,c,program_type=Environment) as env:
            p=c.program
            await env.prepare()
            original=await env.warm()
            await env.younger(original)
            await env.feedback_original(original,True,'used-correct')
            await env.controls(tage=True)
            correct=await env.query_iteration(p.old_iteration)
            old=c.consume(correct,p.old_iteration,'after-correct')
            c.check(c.consumers[0]['weights'],old.original.read.weights,
                'late correct original agreement preserves the complete learned experience')
            young=await env.younger(correct)
            young_token=c.save(young)
            before=c.bank.statistical_snapshot(young_token).read.weights[3]
            await env.feedback_original(correct,False,'used-wrong')
            await env.controls(tage=True)
            wrong=await env.query_iteration(p.old_iteration)
            slot,value=c.provider(wrong)
            changed=c.consume(wrong,p.old_iteration,'after-wrong')
            c.check(True,all(a!=b for a,b in zip(old.original.read.weights,changed.original.read.weights,strict=True)),
                'new original iteration consumes the old wrong outcome in all five families')
            c.check((1,1),(value.prediction.used[slot],value.prediction.directions[slot]),
                'declared warm experience remains a discriminating strong consumer after one error')
            new_young=await env.query_iteration(p.young_iteration)
            young_value=c.consume(new_young,p.young_iteration,'young-after-wrong')
            c.private_loop.append(dict(iteration=p.young_iteration,before=before,
                after=young_value.original.read.weights[3],old_iteration=p.old_iteration))
        coverage.evidence=c.finish_loop(wrong)
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
