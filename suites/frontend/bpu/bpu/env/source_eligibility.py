"""Real reset/recovery, public task cancellation and predicate waits only."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json

from toffee import TransferState
from suites.frontend.bpu.bpu.env.bounded_sources import bounded_program
from suites.frontend.bpu.bpu.env.main_service import branch
from suites.frontend.bpu.bpu.model.main_service import PC,STREAM_PC
from suites.frontend.bpu.bpu.model.window_lifetime import LifetimeError
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.checker.source_eligibility import EligibilityChecks

OLD_TARGET,YOUNG_TARGET=PC+0xA00,PC+0x800


def transaction(source,target):
    return BpuBatchTraining(source.prediction.start_pc,deepcopy(source.meta.resolve),
                            (branch(1,target,3,wrong=True),))


def fingerprint(value):return sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


async def new_epoch(env):
    before=env.checker.last_tick
    await env.agent.set_ready(prediction=False,meta=True)
    await env.agent.configure_predictors(tage=True,settle=True)
    await env.agent.reset(STREAM_PC)
    admissions=await env.accept_window(STREAM_PC)
    anchor=await env.agent.next_transaction(start_pc=STREAM_PC,after_tick=before)
    assert admissions==((anchor.prediction_tick,env.checker.source_token(anchor).sequence),)
    env.anchor=anchor
    await env.pause()
    await env.agent.configure_predictors(tage=False,settle=True)
    return await env.capture_source(PC)


async def idle_boundary(env):
    await env.observation.wait('source-gate-input-is-actually-idle',lambda _:not env.agent.training_driver.has_outstanding
        and env.checker.current_row is not None and not env.checker.current_row['inputs']['training']['valid'])


async def consumer(env,target):
    source=await env.capture_source(PC)
    token=env.checker.source_token(source)
    assert token.middle.branch.target==target
    return dict(source=token.sequence,prediction_tick=source.prediction_tick,metadata_tick=source.meta_tick,
                verified_middle_target=token.middle.branch.target,independent_pipeline_comparison_active=True)


async def run(agent,program,evidence):
    checks=EligibilityChecks(program);check=checks.check;env=None;originals=[]
    try:
        async with bounded_program(agent,late_enabled_at_boot=True) as (env,anchor):
            driver=agent.training_driver
            old=await env.capture_source(PC)
            old_token=env.checker.source_token(old);old_window=env.checker.receipt_window(old)
            originals.append((old,deepcopy(old.meta.resolve),deepcopy(old.meta.redirect)))
            tx=None;rejection=None;fresh=None
            if program.mode in ('flushed-before-launch','changed-before-launch','reset-before-launch','cancel-before-launch','defer-then-accept'):
                tx=env.prepare_input(old,OLD_TARGET)
            evidence.update(original_source=old_token.sequence,original_window=old_window.sequence,
                original_epoch=old_window.epoch,original_full_metadata_sha256=fingerprint(old.meta.resolve))
            if program.reset:
                evidence['before_reset_all_actual_S1']=env.checker.windows.counts['S1-admission']
                fresh=await new_epoch(env)
                originals.append((fresh,deepcopy(fresh.meta.resolve),deepcopy(fresh.meta.redirect)))
                check(True,env.checker.windows.ledger.epoch>old_window.epoch,'actual native reset ended the old source epoch')
            elif program.mode.startswith('flushed-'):
                env.anchor=anchor
                fresh=await env.capture_source(PC)
                originals.append((fresh,deepcopy(fresh.meta.resolve),deepcopy(fresh.meta.redirect)))
                cancellations=[item for item in env.checker.windows.redirects if old_token.sequence in item['discarded']]
                check(1,len(cancellations),'a real older redirect cancelled exactly this original source')
                evidence['actual_cancellation']=cancellations[0]
            elif program.mode=='valid-old-late':
                fresh=await env.capture_source(PC)
                originals.append((fresh,deepcopy(fresh.meta.resolve),deepcopy(fresh.meta.redirect)))
                young_token=env.checker.source_token(fresh)
                check(True,young_token.sequence!=old_token.sequence,'same PC still has two different original occurrences')
                check(old.prediction.start_pc,fresh.prediction.start_pc,'both original occurrences belong to the declared same PC')
                # The real redirect advances history. Source identity must
                # neither assume equal PHR nor rewrite it to manufacture a tie.
                evidence['public_history_metadata_equal']=old.meta.resolve['phr']==fresh.meta.resolve['phr']
                evidence['complete_metadata_equal']=old.meta.resolve==fresh.meta.resolve
                await env.send_prepared(fresh,env.prepare_input(fresh,YOUNG_TARGET))
                await env.send_prepared(old,env.prepare_input(old,OLD_TARGET))
                check([young_token.sequence,old_token.sequence],[r['source'] for r in env.checker.actual_inputs],
                      'legal younger then older feedback is accepted in declared order')
                evidence['consumer']=await consumer(env,OLD_TARGET)
            if program.mode in ('cancel-before-launch','defer-then-accept'):
                attempts=[];before=deepcopy(env.checker.current_row['complete_training'])
                admission_open=False
                def admission(value):
                    attempts.append(env.checker.last_tick)
                    if not admission_open:return False
                    env.checker.gate.admit(value);env.checker.plan_feedback(old,value);return True
                with driver.admit_when(admission):
                    handle=driver.send(tx);env.submissions.append(handle)
                    await env.observation.wait('two-real-deferrals-before-any-encoding',lambda _:len(attempts)>=2)
                    check(TransferState.PENDING,handle.state,'a deferred input has no accepted response ownership')
                    check(before,env.checker.current_row['complete_training'],'deferred input has not encoded or changed payload pins')
                    check(0,len(env.checker.actual_inputs),'deferred input has no native accept')
                    evidence.update(deferral_attempts_before_launch=len(attempts),
                        deferred_payload_sha256=fingerprint(env.checker.current_row['complete_training']),
                        original_idle_payload_sha256=fingerprint(before))
                    if program.mode=='cancel-before-launch':
                        handle.cancel()
                        try:await handle
                        except asyncio.CancelledError:pass
                        else:raise AssertionError('explicit cancellation did not reach its waiter')
                        await idle_boundary(env)
                        check(TransferState.CANCELLED,handle.state,'only this unaccepted task was cancelled')
                        check(None,handle.accepted_event,'cancelled input never reached RTL')
                    else:
                        admission_open=True
                        event=await handle
                        check(event.tick,env.checker.actual_inputs[-1]['tick'],'driver and native acceptance identify one event')
                if program.mode=='cancel-before-launch':
                    env.checker.gate.cancel_unlaunched()
                    fresh=await env.capture_source(PC)
                    originals.append((fresh,deepcopy(fresh.meta.resolve),deepcopy(fresh.meta.redirect)))
                    await env.send_prepared(fresh,env.prepare_input(fresh,YOUNG_TARGET))
                    evidence['consumer']=await consumer(env,YOUNG_TARGET)
                else:
                    await env.pause();evidence['consumer']=await consumer(env,OLD_TARGET)
                evidence['driver_after_action']='usable'
            elif program.mode!='valid-old-late':
                before=len(env.checker.actual_inputs)
                try:
                    if program.mode.endswith('before-prepare'):
                        env.checker.gate.prepare(old_window,transaction(old,OLD_TARGET),receipt_metadata=old.meta.resolve)
                    else:
                        if program.mode=='changed-before-launch':tx.resolve_meta['phr']['phrLowBits']^=1
                        await env.send_prepared(old,tx)
                except LifetimeError as error:rejection=error
                else:raise AssertionError('invalid original input was not rejected')
                check(before,len(env.checker.actual_inputs),'rejected input cannot be accepted by hardware')
                check(0,env.checker.gate.launches,'rejection occurs before encoding and writes')
                check(False,driver.has_outstanding,'rejected input has no remaining task owner')
                check(None,env.checker.gate.pending,'no unlaunched original is left outside its scope')
                evidence['rejection']=dict(reason=rejection.reason,state=rejection.state,error_type=type(rejection).__name__)
                if program.terminal_driver:
                    pending=transaction(fresh if fresh is not None else old,YOUNG_TARGET)
                    try:driver.send(pending)
                    except RuntimeError as following:
                        check(True,following.__cause__ is rejection,'failed driver keeps the original exception as its cause')
                    else:raise AssertionError('failed driver unexpectedly accepted more work')
                    await idle_boundary(env)
                    evidence['driver_after_action']='failed-with-original-error'
                else:
                    await env.send_prepared(fresh,env.prepare_input(fresh,YOUNG_TARGET))
                    evidence['consumer']=await consumer(env,YOUNG_TARGET)
                    evidence['driver_after_action']='usable'
            check(program.accepts,len(env.checker.actual_inputs),'all and only declared native inputs were accepted')
            check(True,all(s.meta.resolve==r and s.meta.redirect==d for s,r,d in originals),'all original snapshots remain immutable')
            check(False,driver.has_outstanding,'all submitted tasks have a terminal owner state')
            check(None,env.checker.gate.pending,'single training cache is not left occupied')
            evidence.update(status='PASS',actual_inputs=deepcopy(env.checker.actual_inputs),
                accepted=env.checker.gate.accepts,launches=env.checker.gate.launches,
                peak_live_windows=env.checker.windows.peak,all_actual_S1=env.checker.windows.counts['S1-admission'],
                source_ledger=env.checker.windows.ledger.state(),original_snapshots_unchanged=True,
                no_commit_inferred=True,full_FTQ_reachability_proved=False)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error),
            differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]])
        raise
    finally:
        evidence.update(program=program.state(),checks=checks.summary(),hardware_feature_PASS_granted=False)
