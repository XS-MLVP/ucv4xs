"""Public feedback and actual full-metadata readback at every legal CFI position."""

from bpuverify.common.coverage.exports import write_functional_coverage
from dataclasses import asdict
import json
from pathlib import Path

from toffee import CoverageDatabase
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback, BpuRedirect
from bpuverify.bpu.case.abtb.alias_plan import checkpoint_route
from bpuverify.bpu.case.abtb.timeouts import bounded
from bpuverify.bpu.checker.abtb.stream import PairChecks, PairObservation
from bpuverify.bpu.model.abtb.final_not_taken import fall_through
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.model.alignment import PHASES
from bpuverify.bpu.coverage.alignment import coverage


async def check_training_alignment(agent, output, case):
    checker = PairChecks(dict(scope='real dual-alignment training vector and all conditional counter paths',
        **asdict(case)))
    observation = PairObservation(agent, checker)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    group = coverage()
    events = []

    async def wait(operation, label, cycles=2048):
        return await bounded(agent, checker, operation, label, cycles)

    async def recover(target, source):
        checker.compare((target - 1) & ~7, source.prediction.start_pc & ~7,
            field='genuine_same_halfblock_checkpoint')
        accepted = await wait(agent.redirect(BpuRedirect(target, source.meta.redirect,
            cfi_pc=target - 1, taken=0, branch_type=1)), 'accepted real recovery', 32)
        return await wait(agent.next_transaction(start_pc=target, after_tick=accepted, limit=512),
            'actual target transaction after accepted recovery', 1024)

    try:
        await observation.__aenter__()
        route = checkpoint_route(case.pc)
        await wait(agent.reset(route['cold_lead']), 'reset before all passive references', 8192)
        cold = await wait(agent.next_transaction(start_pc=route['cold_lead'], limit=8192),
            'genuine cold predecessor', 16384)
        await wait(agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True), 'isolate actual MainBTB training/readback', 32)
        checkpoint = cold
        for target in route['actual_not_taken_checkpoint_targets']:
            checkpoint = await recover(target, checkpoint)
        actual = await recover(case.pc, checkpoint)
        initial = actual
        before = None
        for phase, taken, expected_counter in PHASES:
            checker.phase = phase
            predicted_taken = int(before is not None and before >= 2)
            transaction = BpuBatchTraining(case.pc, actual.meta.resolve,
                (BpuBranchFeedback(case.position, case.target, 1, taken=taken,
                    mispredict=int(predicted_taken != taken)),))
            checker.plan_feedback(transaction)
            await wait(agent.train_batch_with_prediction_pause(transaction),
                'real full-metadata branch feedback', 256)
            actual = await recover(case.pc, checkpoint)
            _, entry = mbtb_meta_for_position(actual, case.position)
            checker.compare(dict(branchType=1, rasAction=0), entry['attribute'],
                field='conditional_entry_in_actual_full_metadata', case_label=case.label)
            checker.compare(expected_counter, entry['counter_value'],
                field='actual_MainBTB_counter_after_real_feedback', case_label=case.label)
            rows = [row for row in checker.records if row['tick'] == actual.meta_tick]
            checker.compare(1, len(rows), field='exact_associated_S3_event')
            final = rows[0]['abtb']['final']
            if expected_counter >= 2:
                wanted = dict(valid=1, pc=case.pc, taken=1, position=case.position,
                    target=case.target, branch_type=1)
            else:
                fallback = fall_through(case.pc)
                wanted = dict(valid=1, pc=case.pc, taken=0, position=fallback['position'],
                    target=fallback['target'], branch_type=0)
            checker.compare(wanted, {key: final[key] for key in wanted},
                field='real_S3_result_agrees_with_conditional_counter', case_label=case.label)
            events.append(dict(phase=phase, counter=expected_counter,
                source=asdict(actual), actual_final_S3={key: final[key] for key in wanted}))
            group.sample(dict(case=case.label, phase=phase), details=False)
            before = expected_counter
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger work', 8)
        await wait(observation.drain(), 'drain and check all pending state', 32)
        checker.raise_failure()
        checker.compare(0, len(checker.feedback_plans), field='all_planned_full_feedback_observed')
        summary = checker.summary()
    finally:
        await observation.aclose()
    # Coverage is committed to disk only after the complete scenario passes.
    write_functional_coverage(CoverageDatabase((group,)), output / 'functional-coverage-training-alignment.json')
    with (output / 'alignment-summary.json').open('x') as stream:
        json.dump(dict(case=asdict(case), label=case.label, passed=True,
            expected_logical_start_pcs=case.logical_start_pcs,
            expected_physical_start_pcs=case.physical_start_pcs,
            actual_accepted_feedback=checker.feedback_accepts,
            checked_phases=events, full_state_summary=summary,
            source_checkpoints=dict(cold=asdict(cold), checkpoint=asdict(checkpoint), initial=asdict(initial)),
            full_cycle_trace_export=False, formal_credit=False, full_FTQ_legality_proven=False), stream, indent=2)
