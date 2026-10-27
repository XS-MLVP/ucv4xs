"""bpuverify.bpu.case.sc.history_training components."""

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
from bpuverify.bpu.checker.sc.history_training import Checks


async def check_history_training(agent, execution, output, case):
    bank, common_valid = case['bank'], case['common_valid']
    pc, positions = 0x40010000 + bank, (4, 7)
    jump_pc = (pc & ~1) - 0x200 if bank else None
    lead = (pc if jump_pc is None else jump_pc) - 64
    sources = sorted({source_pc(lead), source_pc(pc)}
        | (set() if jump_pc is None else {source_pc(jump_pc)}))
    anchors = sorted({source & ~15 for source in sources})
    phr = ZeroHistoryChecker(scope='SC valid-common-history training context')
    sc = HistoryScChecker(case, capacity=8192)
    routes = RouteChecker(phr)
    checks = Checks(sc, phr, routes)
    observation = BpuPhrObservation(agent, phr)
    await observation.__aenter__()
    sc_monitor, history_monitor = ScMonitor(agent), CommonHistoryMonitor(agent)
    sc_monitor.start(execution, observer=sc.capture, controls=sc.capture_controls)
    history_monitor.start(execution, observer=routes.capture)
    report = dict(case=case, pc=pc, positions=list(positions), passed=False,
        source_checkpoints=[], hardware_internal_state_written=False, metadata_fabricated=False,
        complete_FTQ_legality_proven=False, nonzero_common_history_qualified=False,
        full_dirty_overwrite_or_four_key_depth_qualified=False, formal_credit=False)

    async def wait(operation, label):
        return await bounded(agent.dut.clock, operation, cycles=8192, checker=checks, label=label)

    async def capture_target(checkpoints):
        if not common_valid:
            return await wait(revisit(agent, phr, pc, checkpoints[source_pc(pc)]), 'direct common-history-invalid target')
        prefix = await wait(revisit(agent, phr, lead, checkpoints[source_pc(lead)]), 'real sequential prefix checkpoint')
        actual = await wait(agent.next_transaction(start_pc=pc, after_tick=prefix.prediction_tick),
            'real common-history-valid target after uninterrupted prefix')
        return actual

    try:
        await wait(agent.reset(anchors[0]), 'actual reset for all table state references')
        aligned = {}
        for anchor in anchors:
            aligned[anchor] = await wait(agent.next_transaction(start_pc=anchor), 'genuine aligned cold checkpoint')
        checkpoints = {}
        for source in sources:
            checkpoints[source] = aligned[source] if source in aligned else await wait(
                revisit(agent, phr, source, aligned[source - 8]), 'genuine half-block source checkpoint')
            report['source_checkpoints'].append(asdict(checkpoints[source]))
        if jump_pc is not None:
            assert path_hash(jump_pc, pc) == 0
            await wait(agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
                ittage=False, ras=False, settle=True), 'normal MainBTB jump preparation')
            jump_cold = await wait(revisit(agent, phr, jump_pc, checkpoints[source_pc(jump_pc)]), 'real cold jump transaction')
            jump_training = BpuTraining(jump_pc, 0, pc, jump_cold.meta.resolve, branch_type=2)
            await wait(agent.train(jump_training), 'normal jump feedback')
            report['jump_preparation'] = dict(cold=asdict(jump_cold), transaction=asdict(jump_training))
        cold, qualified, steps = await wait(prepare_pair(agent, phr, pc, checkpoints[source_pc(pc)], positions, (2, 3)),
            'real 2/3 provider preparation without SC training')
        report['preparation'] = dict(cold=asdict(cold), qualified=asdict(qualified), steps=steps)
        before = await capture_target(checkpoints)
        expected_providers = tage_provider_signatures(qualified, positions)
        sc.check(expected_providers, tage_provider_signatures(before, positions), field='real_qualified_providers_before_feedback')
        sc.check(common_valid, before.meta.resolve['commonHR']['valid'], field='real_captured_common_history_valid')
        sc.check((0, 0), tuple(before.meta.resolve['commonHR'][key] for key in ('ghr', 'bw')), field='zero_GHR_BW_scope')
        sc.check(((1, 0, 0), (1, 0, 0)), sc_decisions_for_positions(before, positions), field='before_SC_decisions')
        report['before'] = asdict(before)
        transactions = tuple(BpuBatchTraining(pc, before.meta.resolve,
            (BpuBranchFeedback(position, neutral_target(pc, position), 1, taken=0),)) for position in positions)
        await wait(agent.configure_predictors(tage=False, settle=True), 'hold genuine providers during SC feedback')
        sc.phase = 'drive_0'
        sc.plan(transactions)
        ticks = await wait(agent.train_batches_with_prediction_pause(transactions), 'two adjacent real-context feedbacks')
        sc.check([2], [ticks[1] - ticks[0]], field='two_actual_accepts_adjacent')
        sc.check(list(ticks), [row['tick'] for row in sc.accepts], field='driver_monitor_accepts_aligned')
        sc.phase = 'drain_0'
        await wait(agent.pause_prediction_reads(), 'drain selected and untouched table buffers')
        await wait(agent.configure_predictors(tage=True, settle=True), 'enable public provider readback')
        sc.phase = 'readback_0'
        after = await capture_target(checkpoints)
        sc.check(expected_providers, tage_provider_signatures(after, positions), field='both_providers_retained_after_feedback')
        sc.check(common_valid, after.meta.resolve['commonHR']['valid'], field='readback_common_history_context')
        sc.check(((0, 0, 0), (0, 0, 0)), sc_decisions_for_positions(after, positions), field='both_public_SC_decisions_after_feedback')
        samples = []
        rows = {row['tick']: row for row in sc.records}
        for feedback, accepted in enumerate(sc.accepts):
            actual = rows[accepted['tick'] + 2]
            for table in TABLES:
                name = f'{table}_bank{bank}'
                enabled = bool(common_valid or table not in ('globalTable_0', 'bwTable_0'))
                sc.check(int(enabled), actual['buffers'][name]['write']['valid'], field='actual_table_update_gate', table=table)
                samples.append(dict(bank=bank, common_valid=common_valid, table=table,
                    feedback=feedback, outcome='wrote' if enabled else 'blocked'))
        summary = sc.summary()
        sc.check(2, summary['accepted_feedback'], field='two_full_public_feedbacks_checked')
        sc.check(10 if common_valid else 6, summary['full_training_read_responses'], field='all_enabled_table_read_responses_checked')
        for table in ('globalTable_0', 'bwTable_0'):
            names = {f'{table}_bank{bank}'}
            actual_actions = [row for row in sc.actions if row['buffer'] in names]
            sc.check(2 if common_valid else 0, len(actual_actions), table=table, field='actual_common_table_updates')
            if not common_valid:
                sc.check({}, sc.reference.memories[f'{table}_bank{bank}'], table=table, field='invalid_history_keeps_common_table_memory_untouched')
        report.update(passed=True, transactions=[asdict(tx) for tx in transactions], training_ticks=list(ticks),
            after=asdict(after), samples=samples, summary=sc.summary(), phr_summary=phr.summary(), route_checks=status(routes.scoreboard))
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await sc_monitor.aclose()
        await history_monitor.aclose()
        await observation.aclose(resume_streams=False)
        report.update(records=sc.records, preedge_records=sc.control_records, phr_records=phr.records,
            route_records=routes.records, accepts=sc.accepts, actions=sc.actions, drains=sc.drains,
            sc_scoreboard_status=status(sc.scoreboard), phr_scoreboard_status=status(phr.scoreboard))
        dump_trace((output / f"sc-history-gate-bank{bank}-common{common_valid}.json"), report, default=str)
    return report
