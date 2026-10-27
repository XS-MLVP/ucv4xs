"""Real MainBTB feedback controls S3 direction; a natural zero-PHR stream warms AheadBTB."""
from collections import Counter
from dataclasses import asdict
import json
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.case.sc.role_scenarios import revisit
from bpuverify.bpu.case.sc.role_scenarios import source_pc
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.abtb.model.state.counter import TRANSITIONS
from bpuverify.bpu.checker.abtb.checks_zero import IntegratedChecks
from bpuverify.bpu.env.abtb.observation import IntegratedObservation
from bpuverify.bpu.case.abtb.timeouts import bounded
from bpuverify.bpu.case.abtb.recipe import recipe


async def run_natural_counter_sweep(agent, output, case):
    design = recipe(case['pc_bank'])
    a, b, c = (design[name] for name in ('a', 'b', 'c'))
    checker = IntegratedChecks(case)
    observation = IntegratedObservation(agent, checker)
    report = dict(case=case, design=design, formal_credit=False, native_credit=False,
        full_ABTB_bank_SRAM_model_claimed=False, full_FTQ_legality_proven=False,
        hardware_internal_state_written=False, metadata_fabricated=False,
        accepted_fastTrain_expected_to_come_from_natural_loop_not_repeated_external_redirects=True)
    async def wait(operation, label, cycles=8192):
        return await bounded(agent, checker, operation, label, cycles)
    async def capture(pc, label):
        actual = await wait(revisit(agent, checker, pc, checkpoints[pc]), label, 512)
        report.setdefault('public_captures', []).append(dict(phase=checker.phase, **asdict(actual)))
        return actual
    async def train(actual, branches, label):
        tx = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve, branches)
        checker.plan_feedback(tx)
        await wait(agent.train_batch_with_prediction_pause(tx), label, 256)
        report.setdefault('feedback', []).append(dict(phase=checker.phase, transaction=asdict(tx)))
    async def steer(goals):
        # CSR enable changes must not race older speculative fastTrain writes.
        # Keep reads stopped while the actual pending pipeline drains, then
        # change enable; do not destroy or reseed any predictor state.
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger predictions before changing direction', 8)
        await wait(observation.drain(), 'drain real older fastTrain and SRAM writes before changing enable', 32)
        await wait(agent.configure_predictors(abtb=False, settle=True), 'disable early feedback while steering actual MainBTB counters', 32)
        await wait(agent.set_ready(prediction=True, meta=True), 'resume predictions with early feedback disabled', 8)
        actual = await capture(a, 'actual complete A metadata before direction change')
        for step in range(8):
            current = mbtb_counter_for_position(actual, 4)
            if current == goals:
                break
            taken = int(current < goals)
            # If the early conditional is not taken, the later unconditional
            # fallback is the real taken branch in this fetch block.
            branches = (BpuBranchFeedback(4, a, 1, taken=taken, mispredict=int((current >= 2) != bool(taken))), None,
                BpuBranchFeedback(7, b, 3, taken=1, mispredict=0)) if not taken else (
                BpuBranchFeedback(4, a, 1, taken=1, mispredict=int(current < 2)),)
            await train(actual, branches, 'normal actual feedback changes the MainBTB direction')
            actual = await capture(a, 'actual MainBTB counter readback after direction feedback')
            wanted = min(3, current + 1) if taken else max(0, current - 1)
            checker.compare(wanted, mbtb_counter_for_position(actual, 4),
                field='actual_MainBTB_conditional_counter_transition', step=step)
        checker.compare(goals, mbtb_counter_for_position(actual, 4), field='MainBTB_direction_prepared_through_real_feedback')
        await wait(agent.configure_predictors(abtb=True, settle=True), 'enable actual S3 fastTrain into AheadBTB', 32)
        # Exactly one recovery starts this phase. No redirect appears in the
        # following natural-loop windows or between individual predictions.
        return await capture(a, 'start natural loop once after changing real direction')
    def target_transitions(first):
        return [row for row in checker.confirmed[first:]
            if row['bank'] == design['target_abtb_bank'] and row['set_index'] == design['target_abtb_set']
            and row['transition'] in TRANSITIONS and row['feedback']['pc'] == a]
    try:
        await observation.__aenter__()
        pcs = (a, b, c)
        leads = [source_pc(pc) - (8 if not case['pc_bank'] else 0) for pc in pcs]
        await wait(agent.reset(leads[0]), 'actual reset with monitors already active')
        raw_sources = []
        for lead in leads:
            raw_sources.append(await wait(agent.next_transaction(start_pc=lead, limit=1024),
                'genuine cold-stream source checkpoint', 4096))
        # MicroBTB enable gates its read/update, not the parent fallback mux.
        # First capture the genuine cold stream while it is enabled, so its
        # held result is a real cold miss rather than a random reset register.
        await wait(agent.configure_predictors(ubtb=False, abtb=False, mbtb=True,
            tage=False, sc=False, ittage=False, ras=False, settle=True), 'isolate real MainBTB-to-S3 direction', 32)
        if not case['pc_bank']:
            raw_sources = [await wait(revisit(agent, checker, source_pc(pc), original),
                'genuine half-fetch-block source checkpoint', 256)
                for pc, original in zip(pcs, raw_sources, strict=True)]
        checkpoints = dict(zip(pcs, raw_sources, strict=True))
        report['source_checkpoints'] = [asdict(row) for row in raw_sources]
        for pc, target in ((b, c), (c, a)):
            actual = await capture(pc, 'cold metadata for a neutral unconditional fallback edge')
            await train(actual, (BpuBranchFeedback(4, target, 3, taken=1, mispredict=1),),
                'normal feedback prepares one actual fallback edge')
        actual = await capture(a, 'cold conditional self-loop metadata')
        await train(actual, (BpuBranchFeedback(4, a, 1, taken=1, mispredict=1),),
            'normal feedback allocates the conditional self-loop')
        actual = await capture(a, 'actual conditional resident metadata before adding fallback')
        checker.compare(2, mbtb_counter_for_position(actual, 4), field='actual_initial_conditional_MainBTB_counter')
        await train(actual, (BpuBranchFeedback(4, a, 1, taken=0, mispredict=1),),
            'first make the earlier conditional genuinely not taken')
        actual = await capture(a, 'read actual weak-negative conditional before fallback allocation')
        checker.compare(1, mbtb_counter_for_position(actual, 4), field='earlier_branch_genuinely_negative_before_late_allocation')
        await train(actual, (BpuBranchFeedback(4, a, 1, taken=0, mispredict=0), None,
            BpuBranchFeedback(7, b, 3, taken=1, mispredict=1)), 'one actual late mispredict allocates the fallback')
        actual = await capture(a, 'actual metadata must contain both conditional and fallback residents')
        checker.compare(0, mbtb_counter_for_position(actual, 4), field='earlier_conditional_zero_after_late_allocation')
        checker.compare(3, mbtb_meta_for_position(actual, 7)[1]['attribute']['branchType'],
            field='late_MainBTB_fallback_actually_resident_not_only_submitted')
        checker.phase = 'warm_fallback'
        await steer(0)
        for _ in range(2):
            await wait(observation.settle(64), 'warm the actual natural fallback cycle before counter sweep', 128)
            await wait(agent.pause_prediction_reads(), 'commit real fallback entries before conditional self-loop', 32)
        seen = {row['transaction']['pc'] for row in checker.accepts if row['phase'] == 'warm_fallback'
            and row['transaction']['taken'] and row['transaction']['branch_type'] == 3}
        checker.compare({a, b, c}, {a, b, c} & seen, field='all_three_real_fallback_S3_fastTrain_sources_seen')
        report['actual_fallback_fastTrain_pcs'] = sorted(seen)
        for phase, goal, required in (
            ('positive_first', 3, {'inc2_3', 'inc3_3'}),
            ('negative_to_zero', 0, {'dec3_2', 'dec2_1', 'dec1_0', 'dec0_0'}),
            ('positive_from_zero', 3, {'inc0_1', 'inc1_2', 'inc2_3', 'inc3_3'}),
        ):
            checker.phase = phase
            first = len(checker.confirmed)
            await steer(goal)
            for window in range(4):
                await wait(observation.settle(64), 'natural recurrent prediction stream without external recovery', 128)
                await wait(agent.pause_prediction_reads(), 'drain actual AheadBTB writes without redirecting the stream', 32)
                observed = {row['transition'] for row in target_transitions(first)}
                if required <= observed:
                    break
            witnesses = target_transitions(first)
            checker.compare(required, required & {row['transition'] for row in witnesses},
                field='all_required_real_conditional_transitions_in_natural_phase', phase_name=phase)
            accepts = [row for row in checker.accepts if row['phase'] == phase and row['transaction']['pc'] == a
                and row['transaction']['meta']['valid']]
            checker.compare(True, bool(accepts), field='actual_genuine_eligible_target_fastTrain_in_natural_stream')
            report.setdefault('phases', []).append(dict(name=phase, target_transitions=witnesses,
                actual_target_accepts=len(accepts), natural_windows=window + 1))
        checker.phase = 'final_confirmation'
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger predictions for final state checks', 8)
        await wait(observation.drain(), 'confirm all delayed counter and PLRU effects', 16)
        checker.raise_failure()
        witnesses = target_transitions(0)
        counts = Counter(row['transition'] for row in witnesses)
        checker.compare(set(TRANSITIONS), set(counts), field='all_eight_real_integrated_conditional_counter_transitions')
        checker.compare(0, len(checker.feedback_plans), field='every_planned_complete_feedback_observed')
        report.update(passed=True, summary=checker.summary(), transition_counts=dict(counts), selected_cell_transitions=witnesses)
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records, preedge_records=checker.control_records,
            coherent_transactions=checker.coherent_transactions, feedback_accepts=checker.feedback_accepts,
            accepts=checker.accepts, confirmed_transitions=checker.confirmed, gates=checker.gates)
        dump_trace((output / f'natural-integrated-abtb-bank{case["pc_bank"]}.json'), report)
