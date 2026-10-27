"""Real checkpoint rollback/redo at compression capacity, then return retirement."""
from bpuverify.bpu.case.ras.repeat import CALL_PC, POSITION
from bpuverify.bpu.case.ras.common import revisit_from_redirect
from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.env.ras.semantic import RasSemanticEnvironment
from bpuverify.bpu.transaction.types import BpuRedirect, BpuTraining
from bpuverify.bpu.env.ras.program import collect


RETURN_PC = CALL_PC+16


async def prepare_call_stream(agent,retirement,semantic):
    """One naturally learned program shared by call and return recovery tests."""
    await semantic.wait(agent.reset(CALL_PC),'reset')
    initial = await semantic.wait(agent.next_transaction(start_pc=CALL_PC),'cold checkpoint')
    await semantic.wait(agent.configure_predictors(ubtb=False,abtb=False,tage=False,sc=False,
        ittage=False,ras=False,mbtb=True,settle=True),'isolate MainBTB preparation')
    cold_call = await semantic.wait(revisit_from_redirect(agent,CALL_PC,initial.meta.redirect),'cold call source')
    await semantic.wait(agent.train(BpuTraining(CALL_PC,POSITION,CALL_PC,cold_call.meta.resolve,
        branch_type=2,ras_action=2)),'learn actual self-call')
    cold_return = await semantic.wait(revisit_from_redirect(agent,RETURN_PC,cold_call.meta.redirect),'cold return source')
    await semantic.wait(agent.train(BpuTraining(RETURN_PC,POSITION,0x4001f000,cold_return.meta.resolve,
        branch_type=3,ras_action=1)),'learn deliberately different return base target')
    await semantic.wait(agent.configure_predictors(ras=True,settle=True),'enable return-stack prediction')
    boundary = await semantic.wait(agent.redirect(BpuRedirect(CALL_PC,cold_call.meta.redirect)),'start genuine call stream')
    return await collect(retirement,semantic,CALL_PC,2,10,boundary)


async def check_redo_unwind(agent,*,calls,coverage):
    if calls not in (8,9):
        raise ValueError('redo selects the last compressed call or the next group allocation')
    async with RasSemanticEnvironment(agent,coverage=coverage,return_pc=RETURN_PC) as semantic, BpuRetirement(agent,semantic=semantic.reference) as retirement:
        observed = await prepare_call_stream(agent,retirement,semantic)
        retirement.checker.check(True,len(observed)>calls,phase='younger-call-suffix-exists')
        source = observed[calls-1]
        semantic.reference.source_expected(source)
        await semantic.wait(retirement.retire_many([(item,2) for item in observed[:calls-1]]),'retire only the surviving older prefix')
        before = semantic.reference.model.program.calls
        recovery = BpuRedirect(RETURN_PC,source.meta.redirect,cfi_pc=(CALL_PC//8)*8+POSITION,
            taken=1,branch_type=2,ras_action=2)
        boundary = await semantic.wait(agent.redirect(recovery),'restore and redo the actual call')
        await semantic.wait(retirement.retire_many([(source,2)]),'retire the redone call exactly once')
        after = semantic.reference.model.program
        retirement.checker.check(calls,after.calls,phase='younger-calls-discarded-and-one-call-redone')
        retirement.checker.check(True,before>after.calls,phase='rollback-is-not-a-noop')
        retirement.checker.check((1,7) if calls==8 else (2,0),
            (after.head.group%8,after.head.repeat),phase='redo-compression-boundary')
        await semantic.wait(agent.set_ready(prediction=True,meta=True),'resume real return consumers')
        # The split case needs a second real return: first cross the group,
        # then decrement its surviving repeated frame. Await semantic work,
        # not a fixed number of idle simulation cycles.
        returns = await collect(retirement,semantic,RETURN_PC,1,2 if calls==9 else 1,boundary)
        retirement.checker.check(True,1<=len(returns)<calls,phase='bounded-nonempty-unwind')
        await semantic.wait(retirement.retire_many([(item,1) for item in returns]),'retire real repeated returns')
        final = retirement.checker.reference.projection()
        retirement.checker.check((1,calls-len(returns)-1,RETURN_PC),
            (final['ssp'],final['sctr'],final['top']),phase='independent-final-repeated-frame')
        semantic.reference.check_survivors(calls=calls,returns=len(returns),return_pc=RETURN_PC)
        semantic.reference.finish()
        return dict(calls=calls,discarded=before-calls,returns=len(returns),reference=semantic.reference.model.state())
