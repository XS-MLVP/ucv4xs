"""Instruction outcomes independently teach direction and statistical correction."""
from bpuverify.bpu.checker.joint_direction_learning import Checks
from bpuverify.bpu.env.joint_direction_learning import Environment
from bpuverify.bpu.env.statistical_prefix import experiment
from bpuverify.bpu.bundle.joint_direction_learning import joint_learning_binding


async def check_joint_learning(agent,profile,coverage):
    c=Checks(profile,coverage)
    try:
        async with experiment(agent,c,program_type=Environment,binding_factory=joint_learning_binding) as env:
            p=c.program
            strong=await env.establish_joint_experience()
            await env.younger(strong)
            await env.feedback_original(strong,True,'used-correct')
            c.expected_provider=7
            correct=await env.query_iteration(p.old_iteration)
            c.provider(correct);kept=c.consume(correct,p.old_iteration,'after-correct')
            c.check(c.consumers[1]['weights'],kept.original.read.weights,'SC no-read agreement preserves complete correction experience')
            await env.younger(correct)
            await env.feedback_original(correct,False,'used-wrong')
            c.expected_provider=6
            wrong=await env.query_iteration(p.old_iteration)
            slot,value=c.provider(wrong);changed=c.consume(wrong,p.old_iteration,'after-wrong')
            c.check(True,all(a!=b for a,b in zip(kept.original.read.weights,changed.original.read.weights,strict=True)),
                'the wrong original changes all correction families while TAGE independently weakens')
            c.check((1,1),(value.prediction.used[slot],value.prediction.directions[slot]),'fresh correction remains discriminating after one genuine error')
            young=await env.query_iteration(p.young_iteration)
            result=c.consume(young,p.young_iteration,'young-after-wrong')
            c.private_loop.append(dict(iteration=p.young_iteration,before=c.young_private_before,
                after=result.original.read.weights[3],old_iteration=p.old_iteration))
        coverage.evidence=c.finish_joint(wrong)
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
