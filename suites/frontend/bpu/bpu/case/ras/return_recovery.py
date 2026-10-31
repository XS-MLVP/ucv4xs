"""Restore a genuine return, undo younger returns, then replay exactly once."""
from suites.frontend.bpu.bpu.case.ras.redo_unwind import POSITION, RETURN_PC, collect, prepare_call_stream
from suites.frontend.bpu.bpu.env.ras.retirement import BpuRetirement
from suites.frontend.bpu.bpu.env.ras.semantic import RasSemanticEnvironment
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect


async def check_return_recovery(agent,*,calls,storage,coverage):
    if calls not in (8,9) or storage not in ('speculative','retained'):
        raise ValueError('return recovery needs a repeated/group boundary and predecessor lifetime')
    async with RasSemanticEnvironment(agent,coverage=coverage,return_pc=RETURN_PC) as semantic, BpuRetirement(agent,semantic=semantic.reference) as retirement:
        observed = await prepare_call_stream(agent,retirement,semantic)
        retirement.checker.check(True,len(observed)>calls,phase='real-call-checkpoint-exists')
        checkpoint = observed[calls]  # Its pre-operation context owns exactly calls live frames.
        semantic.reference.source_expected(checkpoint)
        surviving = [(source,2) for source in observed[:calls]]
        if storage=='retained':
            await semantic.wait(retirement.retire_many(surviving),'retire calls before real return speculation')
        boundary = await semantic.wait(agent.redirect(BpuRedirect(RETURN_PC,checkpoint.meta.redirect)),
            'restore the surviving call prefix without an extra stack action')
        await semantic.wait(agent.set_ready(prediction=True,meta=True),'allow genuine return consumers')
        returns = await collect(retirement,semantic,RETURN_PC,1,3,boundary)
        source = returns[0]
        semantic.reference.source_expected(source)
        before_depth = len(semantic.reference.model.program.frames)-1
        retirement.checker.check(True,len(returns)>=3,phase='at-least-two-younger-real-returns-to-undo')
        boundary = await semantic.wait(agent.redirect(BpuRedirect(RETURN_PC,source.meta.redirect,
            cfi_pc=(RETURN_PC//8)*8+POSITION,taken=1,branch_type=3,ras_action=1)),
            'restore the oldest real return checkpoint and redo its pop')
        if storage=='speculative':
            await semantic.wait(retirement.retire_many(surviving),'retire older calls only after return recovery')
        await semantic.wait(retirement.retire_many([(source,1)]),'retire the redone actual return once')
        after = semantic.reference.model.program
        retirement.checker.check((calls,calls-1,1,calls-2),
            (after.calls,len(after.frames)-1,after.head.group%8,after.head.repeat),phase='restore-before-pop-algebra')
        retirement.checker.check(True,len(after.frames)-1>before_depth,phase='younger-returns-really-undone')
        await semantic.wait(agent.set_ready(prediction=True,meta=True),'consume the recovered return-stack top')
        following = await collect(retirement,semantic,RETURN_PC,1,2,boundary)
        retirement.checker.check(True,len(following)+1<calls,phase='surviving-real-frame-remains')
        await semantic.wait(retirement.retire_many([(item,1) for item in following]),'retire post-recovery genuine returns')
        semantic.reference.check_survivors(calls=calls,returns=1+len(following),return_pc=RETURN_PC)
        semantic.reference.finish()
        return dict(calls=calls,storage=storage,cancelled_returns=len(returns)-1,
            returned=1+len(following),reference=semantic.reference.model.state())
