"""Use genuine cold sources, natural duplicate reads and public S1 control."""
import asyncio
from copy import deepcopy
from suites.frontend.bpu.bpu.env.bounded_sources import bounded_program
from suites.frontend.bpu.bpu.env.main_original_lifetime import close_pressure
from suites.frontend.bpu.bpu.env.main_service import branch
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.mbtb.model.semantic import coordinate
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.bundle.main_duplicate_cleanup import binding
from suites.frontend.bpu.bpu.checker.main_duplicate_cleanup import Checks
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor
from suites.frontend.bpu.bpu.bundle.main_service import main_service_binding
from suites.frontend.bpu.bpu.monitor.main_duplicate_cleanup import PreparationReceipts


def matching(token,position):
    return tuple((way,e) for row in source_entries(token.lookup) for way,e in enumerate(row) if e.hit and e.position==position)


async def prepare(env,p,helper,evidence):
    # No return to an older setup anchor: every saved cold original stays live.
    a=await env.capture_source(p.pc);b=await env.capture_source(p.pc)
    neighbor=await env.capture_source(p.neighbor)
    for s in (a,b,neighbor):
        token=env.checker.source_token(s)
        assert not any(e.hit for row in source_entries(token.lookup) for e in row)
    await env.teach(a,branch(p.position,p.old_target,3,wrong=True))
    await env.teach(neighbor,branch(1,p.neighbor+0x1200,1,wrong=True))
    current=await env.capture_source(p.neighbor)
    await env.teach(current,branch(1,p.neighbor+0x1200,1,taken=False,wrong=True))
    offset=await env.capture_source(p.query_neighbor)
    await env.teach(offset,branch(3,p.neighbor_target,3,wrong=True))
    later=await env.capture_source(p.query_neighbor)
    token=env.checker.source_token(later)
    assert [(w,e.kind,e.counter) for w,e in matching(token,3)]==[(0,3,2)]
    env.checker.windows.ledger.live(env.checker.receipt_window(b))
    evidence['late_cold_qualified_before_send']=True
    retouch=None
    if p.inflight:
        retouch=later;later=await env.capture_source(p.query_neighbor)
        receipts=PreparationReceipts(env.checker)
        async with ServiceMonitor(env.agent,receipts,binding=main_service_binding(env.agent,alignment=0,bank=0)) as monitor:
            first=await env.send_input(retouch,env.prepare_feedback(retouch,branch(3,p.intermediate_neighbor_target,3,wrong=True)),drain=False)
            second=await env.send_input(b,env.prepare_feedback(b,branch(p.position,p.target,3,wrong=True)))
            monitor.raise_failure()
        assert first.tick<second.tick
        assert len(receipts.offers)==len(receipts.services[0])==2
        assert receipts.offers[1]['tick']<=receipts.services[0][0]['tick']
        evidence['preparation_overlap']=dict(first_accept=first.tick,second_accept=second.tick,**receipts.state())
    else:await env.teach(b,branch(p.position,p.target,3,wrong=True))
    kept=(a,b,neighbor,later) if retouch is None else (a,b,neighbor,retouch,later)
    return kept,later


async def run(agent,p,coverage,evidence):
    env=observer=window_task=None;originals=[];duplicate=None
    try:
        async with bounded_program(agent,capacity=16) as (env,helper):
            sources,learning=await prepare(env,p,helper,evidence)
            originals=[(s,deepcopy(s.meta.resolve),deepcopy(s.meta.redirect)) for s in sources]
            coverage.reach('qualified-cold-originals');coverage.reach('distinct-branch-shadow-turnover')
            model=env.checker.model.sources.main
            frame=model.lookup_snapshot(p.pc)
            entries=frame.banks[0].entries
            assert [(e.position,e.target.at(p.pc)) for e in entries]==[(p.position,p.target),(p.position,p.old_target)]
            coverage.reach('natural-duplicate-versions')
            observer=Checks(env,p)
            async with ServiceMonitor(agent,observer,binding=binding(agent)) as monitor:
                primary=None
                try:
                    # Redirect while held S1 is disabled; S2 is never forced.
                    owner=env.anchor;request=BpuRedirect(p.pc,owner.meta.redirect,cfi_pc=owner.prediction.start_pc+1)
                    env.checker.plan_redirect(owner,request);boundary=await agent.redirect(request)
                    await env.observation.wait('duplicate-query-held-at-public-S1',lambda c:
                        (c.model.stages[0] is not None and c.model.stages[0].pc==p.pc
                         and c.model.stages[1:]==(None,None)))
                    before=len(env.checker.actual_inputs)
                    window_task=asyncio.create_task(env.accept_window(p.pc),name='one-native-duplicate-consumer')
                    if p.concurrent:
                        tx=env.prepare_feedback(learning,branch(3,p.updated_neighbor_target,3,wrong=True))
                        def admission(transaction):
                            env.checker.raise_failure()
                            first,second,_=env.checker.model.stages
                            if second is None or second.pc!=p.pc:
                                if first is not None and first.pc==p.pc:return False
                                raise AssertionError('the duplicate consumption opportunity already passed before learning launch')
                            env.checker.gate.admit(transaction);env.checker.plan_feedback(learning,transaction);return True
                        with agent.training_driver.admit_when(admission):
                            handle=agent.training_driver.send(tx);env.submissions.append(handle);accepted=await handle
                        evidence['overlap_training_accept']=dict(tick=accepted.tick,source=env.checker.source_token(learning).sequence)
                    receipts=await window_task;window_task=None
                    duplicate=await agent.next_transaction(start_pc=p.pc,after_tick=boundary)
                    env.checker.source_token(duplicate)
                    assert receipts==((duplicate.prediction_tick,env.checker.source_token(duplicate).sequence),)
                    observer.check([(0,3),(1,3)],[(w,e.kind) for w,e in matching(env.checker.source_token(duplicate),p.position)],
                        'actual independently checked metadata contains both same-position versions')
                    coverage.reach('genuine-duplicate-consumer',tick=duplicate.meta_tick)
                    clears=[r for r in observer.parents if r['cleanup']['valid']]
                    observer.check(1,len(clears),'one genuine duplicate consumption produces one destination clear')
                    observer.check((coordinate(p.pc)[2],2),(clears[0]['cleanup']['row'],clears[0]['cleanup']['mask']),
                        'priority survivor is retained and the other destination cleared')
                    coverage.reach('actual-destination-clear',operation=clears[0])
                    observer.check(p.concurrent,bool(clears[0]['learning']['valid']),
                        'independent learning and cleanup really overlap, or form the declared control')
                    if p.concurrent:observer.check((coordinate(p.neighbor)[2],1),
                        (clears[0]['learning']['row'],clears[0]['learning']['mask']),'independent branch uses its own destination')
                    if p.concurrent:observer.check(clears[0]['tick'],evidence['overlap_training_accept']['tick'],
                        'genuine learning acceptance coincides with the actual duplicate cleanup stage')
                    observer.check(int(p.concurrent),len(env.checker.actual_inputs)-before,'exactly the declared independent input count')
                    coverage.reach('declared-independent-learning-overlap')
                    await env.pause();monitor.raise_failure()
                    observer.check(True,observer.complete(),'all actual destination services completed')
                    coverage.reach('complete-destination-services')
                    env.anchor=duplicate
                    survivor=await env.capture_source(p.pc);token=env.checker.source_token(survivor)
                    observer.check([(0,3)],[(w,e.kind) for w,e in matching(token,p.position)],'only the correct duplicate survivor remains')
                    observer.check(p.target,token.middle.branch.target,'surviving full target is not silently replaced by the old duplicate')
                    neighbor=await env.capture_source(p.query_neighbor);token=env.checker.source_token(neighbor)
                    wanted=p.updated_neighbor_target if p.concurrent else p.prepared_neighbor_target
                    observer.check(wanted,token.middle.branch.target,'other branch learning survives cleanup')
                    coverage.reach('fresh-survivor-and-neighbor')
                    observer.check(True,all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),'all original metadata stays immutable')
                    coverage.reach('immutable-originals');coverage.finish()
                    evidence.update(status='PASS',fresh_survivor=dict(tick=survivor.prediction_tick,target=p.target),
                        fresh_neighbor=dict(tick=neighbor.prediction_tick,target=wanted))
                except BaseException as error:primary=error;raise
                finally:await close_pressure(window_task,primary);window_task=None
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        evidence.update(program=p.state(),observer=None if observer is None else observer.summary(),
            actual_duplicate=None if duplicate is None else dict(tick=duplicate.prediction_tick,meta_tick=duplicate.meta_tick),
            original_snapshots_unchanged=all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),
            all_qualified_inputs=[] if env is None else env.checker.actual_inputs,
            source_redirects=[] if env is None else env.checker.windows.redirects,
            all_actual_S1=None if env is None else env.checker.windows.counts['S1-admission'],
            peak_live=None if env is None else env.checker.windows.peak,no_commit_inferred=True,full_FTQ_reachability_proved=False)
