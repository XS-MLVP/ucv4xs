"""bpuverify.bpu.case.bypass.history components."""

from collections import Counter
from dataclasses import asdict
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.case.abtb.timeouts import bounded
from bpuverify.bpu.case.bypass.history_plan import recipe
from bpuverify.bpu.checker.bypass.history import NonzeroChecks
from bpuverify.bpu.env.bypass.history import NonzeroObservation


async def run_nonzero_loop(agent, output, *, bank):
    plan = recipe(bank)
    pc, position, fallback = (plan[key] for key in ('pc', 'position', 'fallback'))
    checker = NonzeroChecks(dict(physical_bank=bank, scope='genuine nonzero-PHR recurrent stream'))
    observation = NonzeroObservation(agent, checker)
    report = dict(plan=plan, formal_credit=False, native_credit=False,
        hardware_internal_state_written=False, metadata_fabricated=False,
        full_parent_allocation_policy_modeled=False, full_FTQ_legality_proven=False)
    async def wait(operation, label, cycles=8192):
        return await bounded(agent, checker, operation, label, cycles)
    async def capture(label):
        checker.compare(pc - 1, checkpoint.prediction.start_pc, field='genuine same-halfblock checkpoint PC')
        recovery = BpuRedirect(pc, checkpoint.meta.redirect, cfi_pc=pc-1, taken=0, branch_type=1)
        boundary = await wait(agent.redirect(recovery), label + ': real recovery', 32)
        actual = await wait(agent.next_transaction(start_pc=pc, after_tick=boundary, limit=256), label, 512)
        report.setdefault('public_captures', []).append(dict(phase=checker.phase, **asdict(actual)))
        return actual
    async def train(actual, branches, label):
        transaction = BpuBatchTraining(pc, actual.meta.resolve, branches)
        checker.plan_feedback(transaction)
        await wait(agent.train_batch_with_prediction_pause(transaction), label, 256)
        report.setdefault('feedback', []).append(dict(phase=checker.phase, transaction=asdict(transaction)))
    def branch(taken, mispredict):
        return BpuBranchFeedback(position, pc, 1, taken=taken, mispredict=mispredict)
    def late(mispredict=0):
        return BpuBranchFeedback(fallback, pc, 3, taken=1, mispredict=mispredict)
    async def steer(goal):
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger tasks for direction preparation', 8)
        await wait(observation.drain(), 'drain earlier real fastTrain before disabling it', 32)
        await wait(agent.configure_predictors(abtb=False, settle=True), 'isolate MainBTB direction updates', 32)
        await wait(agent.set_ready(prediction=True, meta=True), 'resume MainBTB metadata capture', 8)
        actual = await capture('actual MainBTB direction before preparation')
        for step in range(8):
            counter = mbtb_counter_for_position(actual, position)
            if counter == goal:
                break
            taken = int(counter < goal)
            first = branch(taken, int((counter >= 2) != bool(taken)))
            await train(actual, (first,) if taken else (first, None, late()), 'normal feedback prepares direction')
            actual = await capture('actual MainBTB direction transition')
            checker.compare(min(3,counter+1) if taken else max(0,counter-1),
                mbtb_counter_for_position(actual,position), field='real_MainBTB_direction_transition', step=step)
        checker.compare(goal, mbtb_counter_for_position(actual,position), field='real_MainBTB_direction_goal')
        await wait(agent.configure_predictors(abtb=True, settle=True), 'enable genuine S3 fastTrain', 32)
        return await capture('start one natural nonzero-history loop')
    try:
        await observation.__aenter__()
        await wait(agent.reset(pc-1), 'genuine reset with all monitors active')
        checkpoint = await wait(agent.next_transaction(start_pc=pc-1, limit=256), 'actual cold same-halfblock checkpoint', 1024)
        report['source_checkpoint'] = asdict(checkpoint)
        checker.compare(0,checkpoint.prediction.taken,field='genuine cold checkpoint not-taken')
        await wait(agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True), 'hold a real cold MicroBTB miss; isolate MainBTB', 32)
        actual = await capture('cold conditional source')
        await train(actual,(branch(1,1),),'allocate actual conditional self-loop')
        actual = await capture('real initial conditional counter')
        checker.compare(2,mbtb_counter_for_position(actual,position),field='initial_conditional_counter')
        await train(actual,(branch(0,1),),'prepare negative conditional before fallback allocation')
        actual = await capture('real negative conditional')
        checker.compare(1,mbtb_counter_for_position(actual,position),field='negative_conditional_counter')
        await train(actual,(branch(0,0),None,late(1)),'allocate genuine later unconditional fallback')
        actual = await capture('both actual MainBTB residents')
        checker.compare((0,3),(mbtb_counter_for_position(actual,position),
            mbtb_meta_for_position(actual,fallback)[1]['attribute']['branchType']),field='both_real_MainBTB_residents')
        for phase,goal in (('warm_fallback',0),('positive_first',3),('negative',0),('positive_again',3)):
            checker.phase=phase
            await steer(goal)
            begin=checker.bypass.last_event.tick
            for _ in range(4):
                await wait(observation.settle(64),'uninterrupted self-loop without external redirects',128)
                await wait(agent.pause_prediction_reads(),'drain real shadow and SRAM writes without recovery',32)
            report.setdefault('natural_windows',[]).append(dict(phase=phase,begin_tick=begin,
                end_tick=checker.bypass.last_event.tick,cycles_per_window=64,windows=4))
        checker.phase='final_confirmation'
        await wait(agent.set_ready(prediction=False,meta=True),'stop younger predictions before finishing',8)
        await wait(observation.drain(),'confirm all accepted delayed effects',16)
        checker.compare((None,None),(checker.counter.pending1,checker.counter.pending2),
            field='all_accepted_fastTrain_tasks_drained')
        checker.compare(0,len(checker.feedback_plans),field='every_complete_planned_feedback_observed')
        checker.compare(True,checker.bypass.nonzero_hash_frames>0,field='real_nonzero_PHR_hashing_observed')
        counts=Counter((row['table'],row['index']%4,row['source']) for row in checker.bypass.writes)
        for table in range(2):
            for source in ('allocation','resident'):
                checker.compare(True,counts[(table,bank,source)]>0,
                    field='actual_target_physical_bank_and_training_source',table=table,bank=bank,source=source)
        report.update(passed=True,ABTB_summary=checker.summary(),bypass_summary=checker.bypass.finish(),
            training_source_counts=[dict(table=t,bank=b,source=s,count=n) for (t,b,s),n in sorted(counts.items())])
    except BaseException as error:
        report['failure']=repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records,preedge_records=checker.control_records,
            coherent_transactions=checker.coherent_transactions,feedback_accepts=checker.feedback_accepts,
            accepts=checker.accepts,confirmed_transitions=checker.confirmed,gates=checker.gates,
            bypass_records=checker.bypass.records,bypass_writes=checker.bypass.writes,
            bank_writes=checker.bypass.bank_writes,SRAM_reads=checker.bypass.SRAM_reads,
            forced_conflicts=checker.bypass.forced_conflicts,
            reset_cache_divergences=checker.bypass.reset_cache_divergences,failed_frame=checker.bypass.failed_frame)
        dump_trace((output/f'integrated-nonzero-bank{bank}.json'), report)
    return report
