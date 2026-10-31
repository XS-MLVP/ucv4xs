"""One original-input/service lifetime, with explicit preparation and checks."""
from suites.frontend.bpu.models.configuration import *
import asyncio
from copy import deepcopy

from suites.frontend.bpu.bpu.env.bounded_sources import bounded_program
from suites.frontend.bpu.bpu.env.main_service import branch
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.main_original_order import PC,STREAM_PC,EARLIER,LATER,TARGETS
from suites.frontend.bpu.bpu.model.main_service import observed_counter
from suites.frontend.bpu.bpu.driver.control import PredictionWindow
from suites.frontend.bpu.bpu.bundle.main_service import main_service_binding
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.monitors.activity import TRAINING_TIMEOUT_CYCLES


async def close_pressure(task,primary=None):
    """Finish owned control work without replacing an existing semantic error."""
    if task is None:return
    if not task.done():task.cancel()
    try:await task
    except asyncio.CancelledError:pass
    except BaseException as cleanup:
        if primary is None:raise
        if cleanup is not primary:primary.add_note(f'pressure cleanup: {cleanup!r}')


async def open_pressure(env,observer,source):
    env.anchor=source
    request=BpuRedirect(STREAM_PC,source.meta.redirect,cfi_pc=source.prediction.start_pc+EARLIER)
    env.checker.plan_redirect(source,request)
    await env.agent.redirect(request)
    future=asyncio.get_running_loop().create_future();observer.close_when_retained=future
    # SyncDriver.send is ordinary awaited work. Keep its task in the env,
    # inheriting the live simulation context, not Execution.external_task.
    handle=asyncio.create_task(env.agent.control_driver.send(PredictionWindow(env.agent._control_values(),future,
        'main-two-originals-latest-retained',TRAINING_TIMEOUT_CYCLES,lambda:observer.failure or env.checker.failure)),
        name='main-original-order-read-window')
    try:
        await env.observation.wait('main-natural-same-bank-read-pressure',lambda _:observer.last is not None
            and bool(observer.last[1]['read']['valid']))
    except BaseException as primary:
        await close_pressure(handle,primary)
        raise
    return handle


async def run_original_lifetime(agent,p,coverage,evidence,*,prepare_sources,checker_factory):
    env=observer=pressure=None;originals=[];accepts=[];source_facts={}
    try:
        async with bounded_program(agent,capacity=16) as (env,helper):
            sources=await prepare_sources(env,helper,p)
            observer=checker_factory(env,p)
            originals=[(source,deepcopy(source.meta.resolve),deepcopy(source.meta.redirect)) for source in sources]
            tokens,source_facts=observer.start(sources);evidence.update(source_facts)
            coverage.reach('real-distinct-originals')
            before=len(env.checker.actual_inputs)
            async with ServiceMonitor(agent,observer,binding=main_service_binding(agent,alignment=0,bank=0)) as monitor:
                primary=None
                try:
                    if p.retained:pressure=await open_pressure(env,observer,sources[1])
                    for index in p.order_indices:
                        env.checker.windows.ledger.live(env.checker.receipt_window(sources[index]))
                        tx=env.prepare_feedback(sources[index],branch(EARLIER,TARGETS[index],3,wrong=True))
                        event=await env.send_input(sources[index],tx,drain=not p.retained)
                        accepts.append(dict(source=tokens[index].sequence,tick=event.tick,target=TARGETS[index]))
                        if not p.retained:
                            await env.observation.wait('main-declared-version-actually-serviced',lambda _:
                                (monitor.raise_failure() is None) and len(observer.entry_services())==len(accepts)
                                and len(observer.written[MAIN_WAYS])==len(accepts))
                    monitor.raise_failure()
                    coverage.reach('source-qualified-inputs')
                    observer.check([tokens[i].sequence for i in p.order_indices],
                        [r['source'] for r in env.checker.actual_inputs[before:]],'actual accepts preserve declared arrival order, not source age')
                    observer.check([r['tick'] for r in accepts],observer.inputs,'public driver and passive monitor identify the same accepts')
                    coverage.reach('declared-arrival-order')
                    if pressure is not None:
                        await pressure;pressure=None
                        observer.check(True,observer.retained_witness is not None,'complete latest version really retained before release')
                    else:observer.check(2,len(observer.entry_services()),'first actual service precedes second learning')
                    coverage.reach('declared-version-visibility')
                    await env.pause()
                    await env.observation.wait('main-all-original-services-delivered',lambda _:observer.complete())
                    monitor.raise_failure()
                    observer.check(p.services,observer.entry_services(),'every actual complete entry service follows the declared visibility boundary')
                    observer.check([],observer.written[1-p.owner],'the independent sibling owner receives no entry service')
                    coverage.reach('complete-entry-services')
                    observer.check([p.direction,p.direction],[observed_counter(r['bits']) for r in observer.directions],
                        'two complete direction proposals only reset the corrected branch owner')
                    observer.check([p.direction,p.direction],[observed_counter(r['bits']) for r in observer.written[MAIN_WAYS]],
                        'both independent direction obligations really reach SRAM')
                    coverage.reach('independent-direction-services')
                    env.anchor=sources[1]
                    sibling=await env.capture_source(PC+EARLIER+1);token=env.checker.source_token(sibling)
                    later=[s for row in source_entries(token.lookup) for s in row if s.hit and s.position==LATER]
                    observer.check([(1,p.sibling_counter)],[(s.kind,s.counter) for s in later],
                        'fresh independently compared lookup preserves the unexecuted sibling')
                    observer.check(False,token.middle.branch.taken,'fresh offset fetch does not jump to the unexecuted sibling')
                    coverage.reach('fresh-unexecuted-sibling')
                    final=await env.capture_source(PC);token=env.checker.source_token(final)
                    observer.check((EARLIER,p.final_target,3),(token.middle.branch.position,token.middle.branch.target,int(token.middle.branch.kind)),
                        'fresh earlier consumer follows the last accepted original resolution')
                    coverage.reach('fresh-final-target')
                    observer.check(True,all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),'complete original snapshots remain immutable')
                    coverage.reach('immutable-originals');coverage.finish()
                    evidence.update(status='PASS',fresh_sibling=dict(tick=sibling.prediction_tick,
                        verified_counter=p.sibling_counter,verified_taken=False),fresh_final=dict(tick=final.prediction_tick,
                        verified_target=p.final_target),independent_pipeline_and_PHR_comparison=True)
                except BaseException as error:
                    primary=error
                    raise
                finally:
                    # All observation is still live during SyncDriver's tail.
                    # Its final actual admissions must enter the same ledger.
                    await close_pressure(pressure,primary)
                    pressure=None
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error),
            differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]])
        raise
    finally:
        evidence.update(program=p.state(),actual_accepts=accepts,observer=None if observer is None else observer.summary(),
            all_actual_S1=None if env is None else env.checker.windows.counts['S1-admission'],
            peak_live=None if env is None else env.checker.windows.peak,
            original_snapshots_unchanged=all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),
            no_commit_inferred=True,full_FTQ_reachability_proved=False)
        if source_facts:
            evidence.update(all_actual_qualified_inputs=deepcopy(env.checker.actual_inputs),
                source_ledger=env.checker.windows.ledger.state(),source_redirects=env.checker.windows.redirects)
