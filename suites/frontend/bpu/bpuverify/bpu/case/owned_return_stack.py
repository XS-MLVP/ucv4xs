"""Complete autonomous instruction lifetimes, with no testcase clock details."""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode

from bpuverify.bpu.env.owned_return_stack import owned_return_environment
from bpuverify.bpu.model.owned_return_stack import CALL,RETURN,CONTINUATION,STATIC_TARGET


async def check_owned_return_stack(agent,program,coverage,evidence):
    async with owned_return_environment(agent,program) as env:
        checker=env.checker
        def check(expected,actual,point):
            checker.raise_failure()
            checker.board.check(expected=expected,actual=actual,context=CheckContext(
                checker.board.name,ScoreboardMode.DIRECT,sequence_id=checker.last_tick,
                request=dict(point=point,profile=program.label,state=checker.model.sources.ras.state())))
        originals=await env.learn()
        frozen=[(s,deepcopy(s.meta.resolve),deepcopy(s.meta.redirect)) for s in originals]
        await agent.configure_predictors(ras=True,settle=True)
        call=await env.capture_source(CALL)
        ret=await env.next_source(RETURN,after_tick=call.prediction_tick)
        call_token,ret_token=checker.source_token(call),checker.source_token(ret)
        bank=checker.model.sources
        call_snapshot,ret_snapshot=bank.return_snapshot(call_token),bank.return_snapshot(ret_token)
        coverage.record('learned-instructions-own-their-originals',call=call.meta_tick,ret=ret.meta_tick)
        check((CALL,2,RETURN),(call_token.pc,int(call_snapshot.decision.branch.action),call_snapshot.decision.branch.target),
            'independently learned call owns the callee')
        check((RETURN,1,CONTINUATION),(ret_token.pc,int(ret_snapshot.decision.branch.action),ret_snapshot.decision.branch.target),
            'the return consumes the actual call address, not its static target')
        check(False,ret_snapshot.decision.branch.target==STATIC_TARGET,'static return target is not the call lifetime')
        check(2*CONTINUATION,ret_snapshot.original.program.head.address,'the return original owns the call frame')
        coverage.record('call-retains-own-return-address',target=CONTINUATION)
        frozen.extend((s,deepcopy(s.meta.resolve),deepcopy(s.meta.redirect)) for s in (call,ret))
        if program.mode=='call-replay':
            await env.recover(call,RETURN,action=2)
            check(2*CONTINUATION,bank.ras.program.head.address,'owned call replays after cancelling the younger return')
            check(False,bank.ras.original_is_live(ret_snapshot.original),'cancelled younger return no longer owns a live operation')
            coverage.record('recovery-replays-only-owned-call',source=call.meta_tick)
            coverage.record('younger-return-is-cancelled',source=ret.meta_tick)
            boundary=checker.last_tick
            ret=await env.next_source(RETURN,after_tick=boundary)
            ret_token=checker.source_token(ret)
            ret_snapshot=bank.return_snapshot(ret_token)
            check(CONTINUATION,ret_snapshot.decision.branch.target,'fresh return consumes only the replayed live call')
            frozen.append((ret,deepcopy(ret.meta.resolve),deepcopy(ret.meta.redirect)))
        elif program.mode=='return-replay':
            await env.recover(ret,CONTINUATION,action=1)
            check(1,len(bank.ras.program.frames),'owned return is replayed once, leaving the original bottom')
            coverage.record('recovery-replays-only-owned-return',source=ret.meta_tick)
        consumer=await env.next_source(CONTINUATION,after_tick=ret.prediction_tick)
        check(CONTINUATION,consumer.meta.perf.start_pc,'complete fresh continuation was independently predicted')
        coverage.record('return-consumes-matching-call',source=ret.meta_tick,continuation=consumer.meta_tick)
        await env.retire(((call,2),(ret,1)))
        check(2,bank.ras.retirements,'each live call and return retires exactly once')
        check((0,0),(bank.ras.committed_head,bank.ras.committed[0].address),'full committed stack returns to its sentinel')
        coverage.record('live-operations-retire-once',accepted=checker.counts['ras-commits'])
        coverage.record('committed-sentinel-restored')
        if program.mode=='return-replay':
            coverage.record('replayed-return-retires-once',source=ret.meta_tick)
        check(True,all(s.meta.resolve==a and s.meta.redirect==b for s,a,b in frozen),'all published originals remain immutable')
        coverage.record('original-metadata-preserved',originals=len(frozen))
        evidence.update(profile=program.label,call_tick=call.meta_tick,return_tick=ret.meta_tick,
            continuation_tick=consumer.meta_tick,return_target=ret_snapshot.decision.branch.target,
            independent_prediction=True,component_inputs_used_as_golden=False,
            compared_cycles=checker.counts['cycles'],commits=checker.counts['ras-commits'],
            retirements=bank.ras.retirements,checked_obligations=list(program.rules))
    coverage.finish()
    evidence.update(status='PASS',closed=coverage.closed)
