"""A qualified input may outlive its prediction; all timing stays in the env."""
from copy import deepcopy
from suites.frontend.bpu.bpu.env.bounded_sources import bounded_program
from suites.frontend.bpu.bpu.env.main_original_order import prepare
from suites.frontend.bpu.bpu.env.main_original_lifetime import open_pressure,close_pressure
from suites.frontend.bpu.bpu.env.main_service import branch
from suites.frontend.bpu.bpu.bundle.main_service import main_service_binding
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor
from suites.frontend.bpu.bpu.model.main_accepted_recovery import PC,STREAM_PC,EARLIER,LATER
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.checker.main_accepted_recovery import Checks
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect


async def run(agent,p,coverage,evidence):
    env=observer=pressure=None;originals=[];accept=None;source_window=None;tokens=()
    try:
        simultaneous=getattr(p,'simultaneous',False)
        async with bounded_program(agent,capacity=16,simultaneous_training_recovery=simultaneous) as (env,helper):
            sources=await prepare(env,helper,p)
            originals=[(s,deepcopy(s.meta.resolve),deepcopy(s.meta.redirect)) for s in sources]
            observer=Checks(env,p);tokens,_=observer.start(sources)
            source=sources[1];source_window=env.checker.receipt_window(source)
            coverage.reach('real-distinct-originals',sources=[t.sequence for t in tokens])
            async with ServiceMonitor(agent,observer,binding=main_service_binding(agent,alignment=0,bank=0)) as monitor:
                primary=None
                try:
                    pressure=await open_pressure(env,observer,source)
                    env.checker.windows.ledger.live(source_window)
                    before=len(env.checker.actual_inputs)
                    tx=env.prepare_feedback(source,branch(EARLIER,p.target,getattr(p,'kind',3),wrong=True))
                    owner=sources[p.restore_index];owner_token=tokens[p.restore_index]
                    request=BpuRedirect(STREAM_PC,owner.meta.redirect,cfi_pc=PC+EARLIER)
                    if simultaneous:
                        observer.request_recovery(owner_token,tokens[1])
                        accepted,recovery_tick=await env.send_input_and_recover(source,tx,owner,request)
                    else:
                        accepted=await env.send_input(source,tx,drain=False)
                    accept=dict(tick=accepted.tick,source=tokens[1].sequence)
                    observer.check(1,len(env.checker.actual_inputs)-before,'only the one genuine original was accepted')
                    coverage.reach('input-qualified-at-recovery' if simultaneous else 'input-qualified-before-recovery',**accept)
                    if p.moment=='retained-record':
                        await env.observation.wait('complete-accepted-copy-retained-before-recovery',lambda _:
                            (monitor.raise_failure() is None) and observer.first_retained is not None)
                    if not simultaneous:
                        env.checker.windows.ledger.live(env.checker.receipt_window(owner))
                        observer.request_recovery(owner_token,tokens[1])
                        env.checker.plan_redirect(owner,request)
                        recovery_tick=await agent.redirect(request)
                    await pressure;pressure=None
                    monitor.raise_failure()
                    observer.check(recovery_tick,observer.recovery['tick'],'public receipt equals actual independently compared recovery')
                    observer.check(not p.cancelled,source_window in env.checker.windows.ledger.active,
                        'original prediction survives only its own recovery, not an older recovery')
                    observer.check(source_window,env.checker.windows.ledger.accepted[-1].source,
                        'already accepted teaching keeps its exact original even after prediction cancellation')
                    coverage.reach('declared-source-fate',recovery=observer.recovery)
                    coverage.reach('declared-learning-recovery-overlap',witness=observer.retained_witness)
                    coverage.reach('accepted-copy-retained-after-recovery')
                    await env.pause()
                    await env.observation.wait('accepted-copy-entry-and-direction-services-complete',lambda _:observer.complete())
                    monitor.raise_failure();coverage.reach('complete-entry-and-direction-services')
                    env.anchor=owner
                    sibling=await env.capture_source(PC+EARLIER+1);token=env.checker.source_token(sibling)
                    later=[s for row in source_entries(token.lookup) for s in row if s.hit and s.position==LATER]
                    observer.check([(1,p.sibling_counter)],[(s.kind,s.counter) for s in later],
                        'cancelled source does not grant learning permission over its unexecuted sibling')
                    observer.check(False,token.middle.branch.taken,'fresh sibling remains not taken')
                    coverage.reach('fresh-unexecuted-sibling',tick=sibling.prediction_tick)
                    final=await env.capture_source(PC);token=env.checker.source_token(final)
                    observer.check((EARLIER,p.target,getattr(p,'kind',3)),(token.middle.branch.position,token.middle.branch.target,int(token.middle.branch.kind)),
                        'fresh public consumer sees accepted target after source fate changed')
                    coverage.reach('fresh-original-branch-target',tick=final.prediction_tick)
                    observer.check(True,all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),
                        'original input and recovery snapshots remain immutable')
                    coverage.reach('immutable-originals');coverage.finish()
                    evidence.update(status='PASS',fresh_sibling=dict(tick=sibling.prediction_tick,counter=p.sibling_counter),
                        fresh_final=dict(tick=final.prediction_tick,target=p.target))
                except BaseException as error:
                    primary=error;raise
                finally:
                    await close_pressure(pressure,primary);pressure=None
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        evidence.update(program=p.state(),actual_accept=accept,observer=None if observer is None else observer.summary(),
            original_snapshots_unchanged=all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),
            source_ledger=None if env is None else env.checker.windows.ledger.state(),
            source_redirects=[] if env is None else env.checker.windows.redirects,
            all_qualified_inputs=[] if env is None else env.checker.actual_inputs,
            all_actual_S1=None if env is None else env.checker.windows.counts['S1-admission'],
            peak_live=None if env is None else env.checker.windows.peak,
            no_commit_inferred=True,full_FTQ_reachability_proved=False)
