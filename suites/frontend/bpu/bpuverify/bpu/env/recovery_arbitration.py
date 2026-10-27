"""Real driver operations; event conditions choose the arbitration window."""
from asyncio import TaskGroup

from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.branch_targets import BranchTargetProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.main_sources import BranchTargetSources
from bpuverify.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback,BpuRedirect

from bpuverify.bpu.checker.recovery_arbitration import RecoveryChecks


async def exercise_recovery(agent,program):
    checks=RecoveryChecks(program)
    phr=BpuPhrChecker(scope='old execution recovery against younger prediction correction',record_limit=8)
    observation=PipelineObservation(agent,checks,sources=BranchTargetSources())
    checks.pipeline=observation.checker
    try:
        async with observation,agent.observe_phr(phr):
            await agent.reset(program.pc)
            warm=await agent.next_transaction(start_pc=program.pc)
            backend=await agent.next_transaction(start_pc=program.backend_pc)
            entry=await agent.next_transaction(start_pc=program.entry_pc)
            checks.own_sources(dict(warm=warm,backend=backend,entry=entry))
            await agent.configure_predictors(ubtb=True,abtb=False,mbtb=False,tage=False,
                sc=False,ittage=False,ras=False,settle=True)
            env=BranchTargetProgram(agent,observation,entry,program.pc)
            await env.pause()
            training=BpuBatchTraining(program.pc,warm.meta.resolve,
                (BpuBranchFeedback(4,program.micro_target,2,taken=1,mispredict=1),))
            checks.pipeline.plan_feedback(warm,training)
            await agent.train_batch(training)
            await env.pause()
            await observation.wait('normal_micro_learning',lambda c:env.effects_compared(c)
                                   and c.model.sources.resident(program.pc))
            enter=BpuRedirect(program.pc,entry.meta.redirect,cfi_pc=program.entry_pc+4,taken=1,branch_type=2)
            checks.pipeline.plan_redirect(entry,enter)
            await agent.redirect(enter)
            checks.arm()

            async def older_recovery():
                tick,cycle=await checks.early_gate
                checks.younger(tick,cycle)
                if program.mode=='after-repair':
                    await checks.repair_gate
                checks.phase='arbitration'
                request=BpuRedirect(program.target,backend.meta.redirect,cfi_pc=program.cfi_pc,
                                    taken=program.taken,branch_type=1)
                checks.pipeline.plan_redirect(backend,request)
                await agent.redirect(request)

            async with TaskGroup() as tasks:
                tasks.create_task(older_recovery())
                tasks.create_task(agent.set_ready(prediction=True,meta=True))
                tasks.create_task(observation.wait('bounded_actual_arbitration_window',lambda c:
                    checks.early_gate.done() and (program.mode=='collision' or checks.repair_gate.done())))
            checks.pipeline.raise_failure()
            checks.check(True,checks.redirect is not None,'the intended backend recovery was actually observed')
            consumer=await agent.next_transaction(start_pc=program.target,after_tick=checks.redirect['tick'])
            checks.consume(consumer)
            await env.pause()
            phr.summary()
            checks.finish()
    except BaseException as error:
        error.add_note('recent bounded arbitration evidence: '+repr(checks.summary()))
        raise
    finally:
        checks.disarm()
    return checks
