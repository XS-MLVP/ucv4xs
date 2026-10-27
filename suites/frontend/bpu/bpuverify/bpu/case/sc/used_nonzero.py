"""Fresh public captures drive genuine SC-used feedback; no synthetic metadata."""
from dataclasses import asdict
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.env.phr.observation import BpuPhrObservation
from bpuverify.bpu.checker.sc.role_scenarios import ZeroHistoryChecker
from bpuverify.bpu.checker.sc.role_scenarios import CombinedChecks
from bpuverify.bpu.case.sc.role_scenarios import source_pc
from bpuverify.bpu.case.sc.role_scenarios import prepare_pair
from bpuverify.bpu.case.sc.role_scenarios import revisit
from bpuverify.bpu.case.sc.role_scenarios import neutral_target
from bpuverify.bpu.case.sc.role_scenarios import status
from bpuverify.bpu.case.sc.scenarios import bounded
from bpuverify.bpu.model.sc.metadata import tage_provider_signatures
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.model.sc.metadata import sc_decisions_for_positions
from bpuverify.bpu.checker.sc.full import FullScChecker
from bpuverify.bpu.monitor.sc.full import FullScMonitor
from bpuverify.bpu.model.sc.used import branch_effects
from bpuverify.bpu.model.sc.used_nonzero_values import expected_public_decisions
from bpuverify.bpu.case.sc.nonzero_scenarios import recipe
from bpuverify.bpu.checker.sc.nonzero_scenarios import Checks
from bpuverify.bpu.monitor.sc.common_routes import CommonHistoryMonitor
from bpuverify.bpu.checker.sc.common_routes import RouteChecker
from bpuverify.bpu.checker.sc.common_state import CommonStateChecker
from bpuverify.bpu.monitor.sc.common_state import CommonStateMonitor
from bpuverify.bpu.model.phr.model import path_hash
PROFILES = dict(disagree=(2, 3), agree=(5, 4))

def single_feedback(pc, capture, *, position, taken):
    index, _ = mbtb_meta_for_position(capture, position)
    sc = capture.meta.resolve['sc']
    predicted = sc['scPred'][index] if sc['useScPred'][index] else sc['tagePred'][index]
    return BpuBatchTraining(pc, capture.meta.resolve, (BpuBranchFeedback(position, neutral_target(pc, position), 1, taken=taken, mispredict=int(predicted != taken)),))

async def check_used(agent, output, profile, *, bank, way, direction):
    goals = PROFILES[profile]
    if bank not in (0, 1) or way not in range(4):
        raise ValueError('physical SC bank/way out of range')
    plan = recipe(bank, direction)
    pc = plan['target']
    sources = sorted({source_pc(address) for address in (pc, plan['prefix'], plan['jump'])})
    anchors = sorted({source & ~15 for source in sources})
    positions = (4, 5) if way in (0, 1) else (6, 7)
    position = {0: 5, 1: 4, 2: 7, 3: 6}[way]
    case = dict(bank=bank, way=way, direction=direction, positions=list(positions), profile=profile, goals=list(goals), scope='genuine SC-used decisions from fresh public captures')
    checker = FullScChecker(case, capacity=4096)
    phr = ZeroHistoryChecker(scope=case['scope'])
    common = CommonStateChecker()
    routes = RouteChecker(phr)
    checks = Checks(checker, phr, common, routes)
    observation = BpuPhrObservation(agent, phr)
    await observation.__aenter__()
    monitor = FullScMonitor(agent)
    monitor.start(agent._execution, observer=checker.capture, controls=checker.capture_controls)
    history_monitor, state_monitor = (CommonHistoryMonitor(agent), CommonStateMonitor(agent))
    history_monitor.start(agent._execution, observer=routes.capture)
    state_monitor.start(agent._execution, observer=common.capture)
    report = dict(case=case, passed=False, formal_credit=False, metadata_fabricated=False, observed_prestate_seeded_reference=False, complete_FTQ_legality_proven=False, deep_SC_used_whole_matrix_closed=False, transactions=[], learning=[], used_feedback=[])

    async def wait(operation, label, cycles=4096):
        return await bounded(agent.dut.clock, operation, cycles=cycles, checker=checks, label=label)

    async def capture_target():
        prefix = await wait(revisit(agent, phr, plan['prefix'], checkpoints[source_pc(plan['prefix'])]), 'genuine conditional-prefix checkpoint', 512)
        actual = await wait(agent.next_transaction(start_pc=pc, after_tick=prefix.prediction_tick), 'uninterrupted real nonzero CommonHR path', 2048)
        checker.check(plan['expected'], actual.meta.resolve['commonHR'], field='independently_expected_nonzero_common_history')
        return actual

    async def readback(checkpoint, providers, label):
        checker.phase = 'readback_' + label
        capture = await capture_target()
        checker.check(providers, tage_provider_signatures(capture, positions), field='real_TAGE_providers_held')
        checker.check(plan['expected'], capture.meta.resolve['commonHR'], field='real_nonzero_history_public_readback')
        checker.check(expected_public_decisions(checker.reference, pc, positions, providers, checker.threshold.values, plan['expected']), sc_decisions_for_positions(capture, positions), field='fresh_SC_metadata_from_reference_SRAM')
        return capture

    async def drive(capture, *, taken, label):
        await wait(agent.configure_predictors(tage=False, settle=True), 'hold TAGE while SC feedback retires', 32)
        transaction = single_feedback(pc, capture, position=position, taken=taken)
        effect, = branch_effects(asdict(transaction))
        checker.phase = 'drive_' + label
        checker.plan((transaction,))
        report['transactions'].append(asdict(transaction))
        before = dict(accepts=len(checker.accepts), actions=len(checker.confirmed_actions), reads=len(checker.confirmed_reads), thresholds=list(checker.threshold.values))
        ticks = await wait(agent.train_batches_with_prediction_pause((transaction,)), 'accept real ' + label, 256)
        checker.phase = 'drain_' + label
        await wait(agent.pause_prediction_reads(), 'retire actual SC reads/writes for ' + label, 32)
        await wait(agent.configure_predictors(tage=True, settle=True), 'restore real public TAGE prediction', 32)
        checker.raise_failure()
        checker.check(1, len(checker.accepts) - before['accepts'], field='one_real_accept_per_fresh_capture')
        checker.check(ticks[0], checker.accepts[-1]['tick'], field='driver_monitor_accept_alignment')
        checker.check(5 * int(effect['read_eligible']), len(checker.confirmed_reads) - before['reads'], field='SC_used_all_five_table_read_gates', classification=label)
        checker.check(5 * int(effect['counter_update']), len(checker.confirmed_actions) - before['actions'], field='SC_used_all_five_table_update_gates', classification=label)
        expected_thresholds = list(before['thresholds'])
        expected_thresholds[way] += effect['threshold_delta']
        checker.check(expected_thresholds, list(checker.threshold.values), field='SC_used_actual_threshold_update_or_hold', classification=label)
        return dict(label=label, accepted_tick=ticks[0], before=asdict(capture), transaction=asdict(transaction), effect=effect, before_counts=before, after_counts=dict(accepts=len(checker.accepts), actions=len(checker.confirmed_actions), reads=len(checker.confirmed_reads), thresholds=list(checker.threshold.values)))
    try:
        for branch_pc, target in ((plan['prefix'] + 2, plan['prefix_target']), (plan['jump'], pc)):
            checker.check(0, path_hash(branch_pc, target), field='real_path_has_zero_PHR_hash')
        await wait(agent.reset(anchors[0]), 'actual reset before all source checkpoints')
        aligned = {anchor: await wait(agent.next_transaction(start_pc=anchor), 'genuine cold aligned source checkpoint') for anchor in anchors}
        checkpoints = {source: aligned[source] if source in aligned else await wait(revisit(agent, phr, source, aligned[source - 8]), 'genuine cold half-block checkpoint') for source in sources}
        checkpoint = checkpoints[source_pc(pc)]
        cold, capture, preparation = await wait(prepare_pair(agent, phr, pc, checkpoint, positions, goals), 'prepare genuine held TAGE provider profile')
        providers = tage_provider_signatures(capture, positions)
        await wait(agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False, ittage=False, ras=False, settle=True), 'hold real providers during path installation', 32)
        for address, cfi_position, target, branch_type in ((plan['prefix'], 2, plan['prefix_target'], 1), (plan['jump'], 0, pc, 2)):
            actual = await wait(revisit(agent, phr, address, checkpoints[source_pc(address)]), 'genuine cold path metadata', 512)
            await wait(agent.train(BpuTraining(address, cfi_position, target, actual.meta.resolve, branch_type=branch_type)), 'normal path branch feedback', 256)
        await wait(agent.configure_predictors(tage=True, sc=True, settle=True), 'enable actual nonzero history prediction', 32)
        capture = await readback(checkpoint, providers, 'before_learning')
        report.update(checkpoint=asdict(checkpoint), cold=asdict(cold), initial=asdict(capture), preparation=preparation)
        for iteration in range(12):
            index, _ = mbtb_meta_for_position(capture, position)
            sc = capture.meta.resolve['sc']
            if sc['useScPred'][index]:
                break
            report['learning'].append(await drive(capture, taken=1, label=f'learning_{iteration}'))
            capture = await readback(checkpoint, providers, f'learning_{iteration}')
        else:
            raise AssertionError(dict(field='bounded_genuine_SC_used_reachability', profile=profile, actual=sc_decisions_for_positions(capture, positions), learning=len(report['learning'])))
        index, _ = mbtb_meta_for_position(capture, position)
        sc = capture.meta.resolve['sc']
        checker.check((1, 1, 1), (sc['scPred'][index], sc['useScPred'][index], sc['sumAboveThres'][index]), field='actual_public_SC_used_reached_without_metadata_edits')
        checker.check(int(profile == 'agree'), sc['tagePred'][index], field='actual_TAGE_agreement_class')
        label = 'used_correct_' + profile
        correct = await drive(capture, taken=1, label=label)
        checker.check((True, profile == 'disagree', False), (bool(correct['effect']['used']), correct['effect']['read_eligible'], correct['effect']['counter_update']), field='correct_SC_used_read_but_no_write_or_no_read')
        report['used_feedback'].append(correct)
        capture = await readback(checkpoint, providers, 'after_used_correct')
        wrong = await drive(capture, taken=0, label='used_wrong_' + profile)
        checker.check((True, True, True), (bool(wrong['effect']['used']), wrong['effect']['read_eligible'], wrong['effect']['counter_update']), field='wrong_SC_used_really_reads_and_updates')
        report['used_feedback'].append(wrong)
        report['final'] = asdict(await readback(checkpoint, providers, 'after_used_wrong'))
        summary = checker.summary()
        checker.check(len(report['transactions']), summary['accepted_feedback'], field='all_fresh_feedback_accounted')
        checker.check(True, bool(report['learning']), field='SC_used_was_learned_in_real_hardware')
        report.update(passed=True, summary=summary, phr_summary=phr.summary(), common_summary=common.summary(), route_checks=status(routes.scoreboard))
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await monitor.aclose()
        await history_monitor.aclose()
        await state_monitor.aclose()
        await observation.aclose(resume_streams=False)
        report.update(records=checker.records, preedge_records=checker.control_records, phr_records=phr.records, accepts=checker.accepts, actions=checker.actions, confirmed_actions=checker.confirmed_actions, reset_cancelled_actions=checker.cancelled_actions, drains=checker.drains, scoreboard_status=status(checker.scoreboard), phr_scoreboard_status=status(phr.scoreboard))
        dump_trace(output / f'sc-used-nonzero-bank{bank}-way{way}-{profile}-{direction}.json.gz', report, default=str)
    return report
