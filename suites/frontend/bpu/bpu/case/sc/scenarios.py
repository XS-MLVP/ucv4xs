"""Transaction-level setup and bounded SC pipeline/lifecycle verification."""
import asyncio
from contextlib import suppress
from dataclasses import asdict
from dataclasses import fields
from itertools import combinations
from itertools import product
import json
from suites.frontend.bpu.runtime.trace import dump_trace

from toffee import AnyOf
from toffee import ClockCycles
from toffee import TaskComplete
from toffee import WallTimeout
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_counter_for_position
from suites.frontend.bpu.bpu.case.sc.metadata import revisit_from_redirect
from suites.frontend.bpu.bpu.model.sc.metadata import sc_decisions_for_positions
from suites.frontend.bpu.bpu.model.sc.metadata import tage_meta_for_position
from suites.frontend.bpu.bpu.model.sc.metadata import tage_provider_signatures
from suites.frontend.bpu.bpu.checker.sc.checker import ScChecker
from suites.frontend.bpu.bpu.monitor.sc.observer import ScMonitor


def cases():
    return [dict(bank=bank, row=row, positions=list(positions), order=order, lifecycle=lifecycle)
        for bank, row, positions, order, lifecycle in product(
            range(2), range(2), combinations((4, 5, 6, 7), 2),
            ('forward', 'reverse'), ('dirty_merge', 'clean_reactivate'))]


SMOKE = (
    dict(bank=0, row=0, positions=[4, 6], order='forward', lifecycle='dirty_merge'),
    dict(bank=1, row=0, positions=[4, 6], order='reverse', lifecycle='dirty_merge'),
    dict(bank=0, row=1, positions=[5, 7], order='forward', lifecycle='clean_reactivate'),
    dict(bank=1, row=1, positions=[4, 7], order='reverse', lifecycle='clean_reactivate'),
)


async def bounded(clock, operation, *, cycles, checker, label):
    task = asyncio.create_task(operation)
    try:
        event = await AnyOf(TaskComplete(task), ClockCycles(clock, cycles), WallTimeout(120))
        if event.source is task:
            checker.raise_failure()
            return event.value
        checker.raise_failure()
        raise AssertionError(dict(case=checker.case, phase=checker.phase, operation=label,
            cycle_limit=cycles, last_tick=None if not checker.records else checker.records[-1]['tick'],
            pending_plans=len(checker.planned), accepted=len(checker.accepts)))
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


async def prepare_pair(agent, pc, positions):
    """Generalize the already qualified two-provider setup, without globals."""
    earlier, later = positions
    first_target, second_target = pc + 0x200, pc + 0x300
    await agent.reset(pc)
    initial = await agent.next_transaction(start_pc=pc)
    await agent.configure_predictors(ubtb=False, abtb=False, tage=True, sc=False,
                                    ittage=False, ras=False, settle=True)
    cold = await revisit_from_redirect(agent, pc, initial.meta.redirect)
    assert cold.prediction.taken == 0
    await agent.train(BpuTraining(pc, earlier, first_target, cold.meta.resolve, branch_type=1))
    first = await revisit_from_redirect(agent, pc, cold.meta.redirect)
    assert mbtb_counter_for_position(first, earlier) == 2
    await agent.train_batch(BpuBatchTraining(pc, first.meta.resolve, (
        BpuBranchFeedback(earlier, first_target, 1, taken=0), None,
        BpuBranchFeedback(later, second_target, 1, taken=1, mispredict=1))))
    residents = await revisit_from_redirect(agent, pc, cold.meta.redirect)
    assert (mbtb_counter_for_position(residents, earlier), mbtb_counter_for_position(residents, later)) == (1, 2)
    assert not tage_meta_for_position(residents, earlier)['hasProvider']
    assert not tage_meta_for_position(residents, later)['hasProvider']
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(pc, residents.meta.resolve,
        (BpuBranchFeedback(earlier, first_target, 1, taken=1, mispredict=1),)))
    single = await revisit_from_redirect(agent, pc, cold.meta.redirect)
    assert tage_meta_for_position(single, earlier)['providerTakenCtr_value'] == 4
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(pc, single.meta.resolve,
        (BpuBranchFeedback(earlier, first_target, 1, taken=0, mispredict=1),)))
    negative = await revisit_from_redirect(agent, pc, cold.meta.redirect)
    assert tage_meta_for_position(negative, earlier)['providerTakenCtr_value'] == 3
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(pc, negative.meta.resolve, (
        BpuBranchFeedback(earlier, first_target, 1, taken=0), None,
        BpuBranchFeedback(later, second_target, 1, taken=0, mispredict=1))))
    both = await revisit_from_redirect(agent, pc, cold.meta.redirect)
    providers = tage_provider_signatures(both, positions)
    assert providers[0][:2] != providers[1][:2]
    assert tuple(item[2] for item in providers) == (2, 3)
    await agent.configure_predictors(sc=True, settle=True)
    qualified = await revisit_from_redirect(agent, pc, cold.meta.redirect)
    assert sc_decisions_for_positions(qualified, positions) == ((1, 0, 0), (1, 0, 0))
    return cold, qualified


async def run_case(agent, execution, output, case, *, fault=None):
    checker = ScChecker(case, fault=fault)
    monitor = ScMonitor(agent)
    monitor.start(execution, observer=checker.capture, controls=checker.capture_controls)
    pc = 0x40000800 + case['row'] * 8 + case['bank']
    positions = tuple(case['positions'])
    report = dict(candidate=True, formal_credit=False, case=case, pruned_pc=pc,
        bank=pc & 1, ftq_global_qualification_proven=False, prediction_overlap_claimed=False,
        arbitration_ready_independently_predicted=False)
    try:
        cold, before = await bounded(agent.dut.clock, prepare_pair(agent, pc, positions),
            cycles=8192, checker=checker, label='qualified two-provider setup')
        report['cold_transaction'], report['captured_transaction'] = asdict(cold), asdict(before)
        providers = tage_provider_signatures(before, positions)
        await bounded(agent.dut.clock, agent.configure_predictors(tage=False, settle=True),
                      cycles=32, checker=checker, label='hold TAGE provider cells')
        report['phases'] = []
        iterations = 2 if case['lifecycle'] == 'clean_reactivate' else 1
        for iteration in range(iterations):
            payloads = (
                BpuBatchTraining(pc, before.meta.resolve,
                    (BpuBranchFeedback(positions[0], pc + 0x200, 1, taken=0), None, None)),
                BpuBatchTraining(pc, before.meta.resolve,
                    (None, None, BpuBranchFeedback(positions[1], pc + 0x300, 1, taken=0))))
            transactions = payloads if case['order'] == 'forward' else payloads[::-1]
            checker.phase = f'drive_{iteration}'
            checker.plan(transactions)
            ticks = await bounded(agent.dut.clock, agent.train_batches_with_prediction_pause(transactions),
                cycles=256, checker=checker, label='adjacent distinct-mask feedback')
            checker.check(2, ticks[1] - ticks[0], field='real_adjacent_driver_accept_spacing')
            actual_accepts = [row['tick'] for row in checker.accepts if row['phase'] == checker.phase]
            checker.check(list(ticks), actual_accepts, field='driver_monitor_accept_association')
            checker.phase = f'drain_{iteration}'
            await bounded(agent.dut.clock, agent.pause_prediction_reads(),
                          cycles=32, checker=checker, label='drain masked SC updates')
            await bounded(agent.dut.clock, agent.configure_predictors(tage=True, settle=True),
                          cycles=32, checker=checker, label='restore provider readback')
            checker.phase = f'readback_{iteration}'
            actual = await bounded(agent.dut.clock, revisit_from_redirect(agent, pc, cold.meta.redirect),
                cycles=256, checker=checker, label='full public SC/provider metadata readback')
            checker.check(providers, tage_provider_signatures(actual, positions), field='all_provider_signatures_retained')
            checker.check(((0, 0, 0), (0, 0, 0)), sc_decisions_for_positions(actual, positions), field='both_SC_decisions_learned')
            report['phases'].append(dict(iteration=iteration, input_capture=asdict(before),
                transactions=[asdict(tx) for tx in transactions], training_ticks=list(ticks), actual=asdict(actual)))
            before = actual
            if iteration + 1 < iterations:
                await bounded(agent.dut.clock, agent.configure_predictors(tage=False, settle=True),
                              cycles=32, checker=checker, label='hold provider for clean reactivation')
        report['summary'] = checker.summary()
        dirty = [row for row in checker.actions if row['kind'] == 'dirty_merge']
        clean = [row for row in checker.actions if row['kind'] == 'clean_reactivate']
        checker.check(3 * iterations, len(dirty), field='real_dirty_merges_each_burst')
        checker.check(3 if iterations == 2 else 0, len(clean), field='real_clean_reactivation')
        report['passed'] = True
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await monitor.aclose()
        report.update(preedge_records=checker.control_records, records=checker.records, accepts=checker.accepts, actions=checker.actions,
            drains=checker.drains, monitor_paths=monitor.paths,
            scoreboard_status={field.name: (repr(value) if field.name == 'first_failure' and value is not None else value)
                for field in fields(checker.scoreboard.status)
                for value in (getattr(checker.scoreboard.status, field.name),)})
        identity = f"b{case['bank']}-r{case['row']}-p{positions[0]}_{positions[1]}-{case['order']}-{case['lifecycle']}"
        if fault is not None:
            identity += '-fault'
        dump_trace((output / f'sc-masked-{identity}.json'), report, default=str)
