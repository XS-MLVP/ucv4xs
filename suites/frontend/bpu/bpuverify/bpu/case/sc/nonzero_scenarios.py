"""bpuverify.bpu.case.sc.nonzero_scenarios components."""

from dataclasses import asdict
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.env.phr.observation import BpuPhrObservation
from bpuverify.bpu.monitor.sc.observer import ScMonitor
from bpuverify.bpu.case.sc.scenarios import bounded
from bpuverify.bpu.model.sc.model import TABLES
from bpuverify.bpu.model.sc.metadata import tage_provider_signatures
from bpuverify.bpu.model.sc.metadata import sc_decisions_for_positions
from bpuverify.bpu.checker.sc.role_scenarios import ZeroHistoryChecker
from bpuverify.bpu.case.sc.role_scenarios import prepare_pair
from bpuverify.bpu.case.sc.role_scenarios import revisit
from bpuverify.bpu.case.sc.role_scenarios import source_pc
from bpuverify.bpu.case.sc.role_scenarios import status
from bpuverify.bpu.case.sc.role_scenarios import neutral_target
from bpuverify.bpu.monitor.sc.common_routes import CommonHistoryMonitor
from bpuverify.bpu.checker.sc.common_routes import RouteChecker
from bpuverify.bpu.checker.sc.history import HistoryScChecker
from bpuverify.bpu.model.sc.history import history_indices
from bpuverify.bpu.checker.sc.common_state import CommonStateChecker
from bpuverify.bpu.monitor.sc.common_state import CommonStateMonitor
from bpuverify.bpu.model.sc.common_state import backwards
from bpuverify.bpu.checker.sc.nonzero_scenarios import Checks


def recipe(bank, direction):
    assert bank in (0, 1) and direction in ('forward', 'backward')
    target = 0x40010000 + bank
    prefix = 0x4000fe00 if direction == 'forward' else 0x40010600
    return dict(target=target, prefix=prefix, prefix_position=2, prefix_target=0x40010040,
        jump=0x40010400, jump_position=0, expected=dict(valid=1, ghr=1, bw=int(direction == 'backward'), imli=0))


async def run_nonzero(agent, execution, output, case):
    bank, direction = case['bank'], case['direction']
    plan, positions = recipe(bank, direction), (4, 7)
    pc = plan['target']
    sources = sorted({source_pc(address) for address in (pc, plan['prefix'], plan['jump'])})
    anchors = sorted({source & ~15 for source in sources})
    phr, common = ZeroHistoryChecker(scope='SC real nonzero common history with full zero PHR'), CommonStateChecker()
    sc = HistoryScChecker(case, capacity=16384)
    routes = RouteChecker(phr)
    checks = Checks(sc, phr, common, routes)
    observation = BpuPhrObservation(agent, phr)
    await observation.__aenter__()
    monitors = (ScMonitor(agent), CommonHistoryMonitor(agent), CommonStateMonitor(agent))
    monitors[0].start(execution, observer=sc.capture, controls=sc.capture_controls)
    monitors[1].start(execution, observer=routes.capture)
    monitors[2].start(execution, observer=common.capture)
    report = dict(case=case, plan=plan, positions=list(positions), passed=False, source_checkpoints=[],
        hardware_internal_state_written=False, metadata_fabricated=False, complete_FTQ_legality_proven=False,
        full_dirty_overwrite_or_four_key_depth_qualified=False, all_history_bits_qualified=False, formal_credit=False)

    async def wait(operation, label):
        return await bounded(agent.dut.clock, operation, cycles=16384, checker=checks, label=label)

    async def capture_target(checkpoints):
        prefix = await wait(revisit(agent, phr, plan['prefix'], checkpoints[source_pc(plan['prefix'])]),
            'genuine cold checkpoint to the real conditional prefix')
        actual = await wait(agent.next_transaction(start_pc=pc, after_tick=prefix.prediction_tick),
            'real conditional prefix, uninterrupted path and final unconditional jump')
        sc.check(plan['expected'], actual.meta.resolve['commonHR'], field='independently_expected_nonzero_common_history')
        return prefix, actual

    try:
        for branch_pc, target in ((plan['prefix'] + 2, plan['prefix_target']), (plan['jump'], pc)):
            assert path_hash(branch_pc, target) == 0
        assert backwards(plan['prefix'] + 2, plan['prefix_target']) == int(direction == 'backward')
        await wait(agent.reset(anchors[0]), 'actual reset before all source and state capture')
        aligned = {}
        for anchor in anchors:
            aligned[anchor] = await wait(agent.next_transaction(start_pc=anchor), 'real cold aligned source')
        checkpoints = {}
        for source in sources:
            checkpoints[source] = aligned[source] if source in aligned else await wait(
                revisit(agent, phr, source, aligned[source - 8]), 'real cold half-block source')
            report['source_checkpoints'].append(asdict(checkpoints[source]))
        cold, qualified, steps = await wait(prepare_pair(agent, phr, pc, checkpoints[source_pc(pc)], positions, (2, 3)),
            'genuine target provider preparation before installing the history path')
        report['preparation'] = dict(cold=asdict(cold), qualified=asdict(qualified), steps=steps)
        await wait(agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
            ittage=False, ras=False, settle=True), 'hold target providers during normal path installation')
        report['path_preparation'] = []
        for address, position, target, branch_type in (
                (plan['prefix'], 2, plan['prefix_target'], 1), (plan['jump'], 0, pc, 2)):
            actual = await wait(revisit(agent, phr, address, checkpoints[source_pc(address)]), 'genuine cold path-branch metadata')
            transaction = BpuTraining(address, position, target, actual.meta.resolve, branch_type=branch_type)
            await wait(agent.train(transaction), 'normal public path-branch training')
            report['path_preparation'].append(dict(cold=asdict(actual), transaction=asdict(transaction)))
        await wait(agent.configure_predictors(tage=True, sc=True, settle=True), 'enable actual history-qualified target prediction')
        prefix, before = await capture_target(checkpoints)
        expected_providers = tage_provider_signatures(qualified, positions)
        sc.check(expected_providers, tage_provider_signatures(before, positions), field='genuine_providers_retained_at_nonzero_context')
        sc.check(((1, 0, 0), (1, 0, 0)), sc_decisions_for_positions(before, positions), field='before_SC_decisions')
        report.update(prefix_before=asdict(prefix), before=asdict(before))
        indices = history_indices(pc, before.meta.resolve['commonHR'])
        sc.check(1, indices['globalTable_0'], field='actual_nonzero_global_row')
        sc.check(int(direction == 'backward'), indices['bwTable_0'], field='actual_direction_dependent_BW_row')
        transactions = tuple(BpuBatchTraining(pc, before.meta.resolve,
            (BpuBranchFeedback(position, neutral_target(pc, position), 1, taken=0),)) for position in positions)
        await wait(agent.configure_predictors(tage=False, settle=True), 'hold qualified providers while SC learns real-history metadata')
        sc.phase = 'drive_0'
        sc.plan(transactions)
        ticks = await wait(agent.train_batches_with_prediction_pause(transactions), 'two adjacent nonzero-history feedbacks')
        sc.check(2, ticks[1] - ticks[0], field='two_actual_feedbacks_adjacent')
        sc.check(list(ticks), [row['tick'] for row in sc.accepts], field='driver_monitor_accepts_aligned')
        sc.phase = 'drain_0'
        await wait(agent.pause_prediction_reads(), 'drain all five history-qualified table buffers')
        await wait(agent.configure_predictors(tage=True, settle=True), 'enable complete public SC readback')
        sc.phase = 'readback_0'
        prefix_after, after = await capture_target(checkpoints)
        sc.check(expected_providers, tage_provider_signatures(after, positions), field='both_original_providers_retained')
        sc.check(((0, 0, 0), (0, 0, 0)), sc_decisions_for_positions(after, positions), field='both_SC_directions_after_feedback')
        frames, samples = {row['tick']: row for row in sc.records}, []
        for feedback, accepted in enumerate(sc.accepts):
            frame = frames[accepted['tick'] + 2]
            for table in TABLES:
                sc.check(1, frame['buffers'][f'{table}_bank{bank}']['write']['valid'], table=table, field='actual_history_qualified_write')
                samples.append(dict(bank=bank, direction=direction, table=table, feedback=feedback))
        summary = sc.summary()
        sc.check(2, summary['accepted_feedback'], field='two_complete_feedbacks')
        sc.check(10, summary['full_training_read_responses'], field='all_five_tables_full_SRAM_responses')
        report.update(passed=True, transactions=[asdict(tx) for tx in transactions], training_ticks=list(ticks),
            prefix_after=asdict(prefix_after), after=asdict(after), samples=samples,
            summary=summary, phr_summary=phr.summary(), common_summary=common.summary(), route_checks=status(routes.scoreboard))
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        for monitor in monitors:
            await monitor.aclose()
        await observation.aclose(resume_streams=False)
        report.update(records=sc.records, preedge_records=sc.control_records, phr_records=phr.records,
            route_records=routes.records, common_records=common.records, common_outcomes=common.outcomes,
            accepts=sc.accepts, actions=sc.actions, drains=sc.drains,
            sc_scoreboard_status=status(sc.scoreboard), phr_scoreboard_status=status(phr.scoreboard),
            common_scoreboard_status=status(common.scoreboard))
        dump_trace((output / f'sc-nonzero-history-bank{bank}-{direction}.json'), report, default=str)
    return report
