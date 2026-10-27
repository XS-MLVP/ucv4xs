"""Fresh public captures drive genuine SC-used feedback; no synthetic metadata."""
from dataclasses import asdict
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
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
from bpuverify.bpu.model.sc.used_zero_values import expected_public_decisions
PROFILES = dict(disagree=(2, 3), agree=(5, 4))

def single_feedback(pc, capture, *, position, taken):
    index, _ = mbtb_meta_for_position(capture, position)
    sc = capture.meta.resolve['sc']
    predicted = sc['scPred'][index] if sc['useScPred'][index] else sc['tagePred'][index]
    return BpuBatchTraining(pc, capture.meta.resolve, (BpuBranchFeedback(position, neutral_target(pc, position), 1, taken=taken, mispredict=int(predicted != taken)),))

async def check_used(agent, output, profile, *, bank, way, checker_factory=None):
    goals = PROFILES[profile]
    if bank not in (0, 1) or way not in range(4):
        raise ValueError('physical SC bank/way out of range')
    pc = 1073758208 + bank
    positions = (4, 5) if way in (0, 1) else (6, 7)
    position = {0: 5, 1: 4, 2: 7, 3: 6}[way]
    case = dict(bank=bank, way=way, positions=list(positions), profile=profile, goals=list(goals), scope='genuine SC-used decisions from fresh public captures')
    checker = FullScChecker(case, capacity=4096) if checker_factory is None else checker_factory(case)
    phr = ZeroHistoryChecker(scope=case['scope'])
    checks = CombinedChecks(checker, phr)
    observation = BpuPhrObservation(agent, phr)
    await observation.__aenter__()
    monitor = FullScMonitor(agent)
    monitor.start(agent._execution, observer=checker.capture, controls=checker.capture_controls)
    report = dict(case=case, passed=False, formal_credit=False, metadata_fabricated=False, observed_prestate_seeded_reference=False, complete_FTQ_legality_proven=False, deep_SC_used_whole_matrix_closed=False, transactions=[], learning=[], used_feedback=[])

    async def wait(operation, label, cycles=4096):
        return await bounded(agent.dut.clock, operation, cycles=cycles, checker=checks, label=label)

    async def readback(checkpoint, providers, label):
        checker.phase = 'readback_' + label
        capture = await wait(revisit(agent, phr, pc, checkpoint), 'fresh public ' + label, 256)
        checker.check(providers, tage_provider_signatures(capture, positions), field='real_TAGE_providers_held')
        checker.check(0, capture.meta.resolve['commonHR']['valid'], field='explicit_zero_common_history_scope')
        checker.check(expected_public_decisions(checker.reference, pc, positions, providers, checker.threshold.values), sc_decisions_for_positions(capture, positions), field='fresh_SC_metadata_from_reference_SRAM')
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
        checker.check(3 * int(effect['read_eligible']), len(checker.confirmed_reads) - before['reads'], field='SC_used_three_active_table_read_gates', classification=label)
        checker.check(3 * int(effect['counter_update']), len(checker.confirmed_actions) - before['actions'], field='SC_used_three_active_table_update_gates', classification=label)
        expected_thresholds = list(before['thresholds'])
        expected_thresholds[way] += effect['threshold_delta']
        checker.check(expected_thresholds, list(checker.threshold.values), field='SC_used_actual_threshold_update_or_hold', classification=label)
        return dict(label=label, accepted_tick=ticks[0], before=asdict(capture), transaction=asdict(transaction), effect=effect, before_counts=before, after_counts=dict(accepts=len(checker.accepts), actions=len(checker.confirmed_actions), reads=len(checker.confirmed_reads), thresholds=list(checker.threshold.values)))
    try:
        await wait(agent.reset(source_pc(pc)), 'actual reset before native SC-used learning')
        checkpoint = await wait(agent.next_transaction(start_pc=source_pc(pc)), 'genuine zero-history checkpoint')
        cold, capture, preparation = await wait(prepare_pair(agent, phr, pc, checkpoint, positions, goals), 'prepare genuine held TAGE provider profile')
        providers = tage_provider_signatures(capture, positions)
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
        report.update(passed=True, summary=summary, phr_summary=phr.summary())
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await monitor.aclose()
        await observation.aclose(resume_streams=False)
        report.update(records=checker.records, preedge_records=checker.control_records, phr_records=phr.records, accepts=checker.accepts, actions=checker.actions, confirmed_actions=checker.confirmed_actions, reset_cancelled_actions=checker.cancelled_actions, drains=checker.drains, scoreboard_status=status(checker.scoreboard), phr_scoreboard_status=status(phr.scoreboard))
        dump_trace(output / f'sc-used-bank{bank}-way{way}-{profile}.json.gz', report, default=str)
    return report
