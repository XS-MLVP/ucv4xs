"""Real accepted feedback and passive monitors; timing stays in existing drivers."""
from copy import deepcopy
from dataclasses import asdict
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.case.abtb.timeouts import bounded
from bpuverify.bpu.case.bypass.public_readback import conditional_source_ways
from bpuverify.bpu.checker.abtb.stream import PairChecks
from bpuverify.bpu.env.abtb.write import WriteObservation as NegativePairObservation
from bpuverify.bpu.case.abtb.readback import matching_sram_readbacks
from bpuverify.bpu.case.abtb.later_taken_plan import PHASES, checkpoint_route, input_qualified, final_comparison, plan, programs, required_operations, selected_program

async def run_later_taken_cycle(agent, output, *, bank, entry_set, coverage=None):
    intent = plan(bank, entry_set)
    checker = PairChecks(dict(bank=bank, entry_set=entry_set, scope='five aliases; distinct later-taken and positive counter transitions'), coverage=coverage)
    observation = NegativePairObservation(agent, checker, max_frames=32768)
    report = dict(plan=intent, passed=False, aliases_executed=0, max_observation_frames=32768, hardware_internal_state_written=False, metadata_fabricated=False, VPI=False, backend='MEM_DIRECT', formal_credit=False, native_credit=False, full_FTQ_legality_proven=False, all256_groups_claimed=False, dirty_full_overwrite_claimed=False, SRAM_readback_association='preedge request to next rising response; both inside alias window', negative_path='final taken=1 at position7; earlier conditional position6 not taken', full_four_way_negative_coverage_proven=False)
    checkpoints = {}

    async def wait(operation, label, cycles=8192):
        return await bounded(agent, checker, operation, label, cycles)

    async def recover(target, checkpoint, label, *, resume=False):
        source = checkpoint.prediction.start_pc
        checker.compare(target - 1 & ~7, source & ~7, field='actual_same_halfblock_checkpoint')
        checker.compare(True, source <= target - 1, field='checkpoint_precedes_CFI')
        transaction = BpuRedirect(target, checkpoint.meta.redirect, cfi_pc=target - 1, taken=0, branch_type=1)
        report.setdefault('recoveries', []).append(dict(payload=transaction.payload(), source=asdict(checkpoint)))
        accepted = await wait(agent.redirect(transaction), label + ': accepted recovery', 32)
        if resume:
            await wait(agent.set_ready(prediction=True, meta=True), label + ': release stream', 8)
        actual = await wait(agent.next_transaction(start_pc=target, after_tick=accepted, limit=512), label, 1024)
        report.setdefault('public_captures', []).append(dict(phase=checker.phase, **asdict(actual)))
        return actual

    async def capture(pc, label):
        return await recover(pc, checkpoints[pc], label)

    async def train(actual, branches, label):
        transaction = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve, tuple(branches))
        checker.plan_feedback(transaction)
        await wait(agent.train_batch_with_prediction_pause(transaction), label, 256)
        report.setdefault('feedback', []).append(dict(phase=checker.phase, transaction=asdict(transaction)))

    async def drain(label):
        await wait(agent.set_ready(prediction=False, meta=True), label + ': stop younger inputs', 8)
        await wait(observation.drain(), label + ': drain delayed tasks', 32)
        checker.compare((None, None), (checker.counter.pending1, checker.counter.pending2), field='all_ABTB_tasks_drained')

    def final_checked(program, source):
        value = source if isinstance(source, dict) else asdict(source)
        rows = [row for row in checker.records if row['tick'] == value['meta_tick']]
        checker.compare(1, len(rows), field='exact_associated_S3_event_exists')
        expected, actual = final_comparison(program, value, rows[0])
        checker.compare(expected, actual, field='actual_final_S3_selected_edge', source=value)
        return actual

    async def prepare(alias):
        conditional, *returns = programs(intent, alias)
        a, b = (conditional['pc'], conditional['target'])
        checker.phase = f'prepare_alias{alias}'
        for program in returns:
            actual = await capture(program['pc'], 'cold actual unconditional cycle edge')
            await train(actual, (BpuBranchFeedback(program['position'], program['target'], 3, taken=1, mispredict=1),), 'allocate real unconditional cycle edge')
            actual = await capture(program['pc'], 'actual unconditional resident after allocation')
            checker.compare(3, mbtb_meta_for_position(actual, 7)[1]['attribute']['branchType'], field='actual_unconditional_cycle_resident')
            final_checked(program, actual)
        actual = await capture(a, 'cold actual fallback')
        await train(actual, (BpuBranchFeedback(7, b, 3, taken=1, mispredict=1),), 'allocate real later fallback')
        actual = await capture(a, 'actual resident fallback')
        checker.compare(3, mbtb_meta_for_position(actual, 7)[1]['attribute']['branchType'], field='actual_later_fallback_resident')
        actual = await capture(a, 'cold actual conditional')
        await train(actual, (BpuBranchFeedback(6, b, 1, taken=1, mispredict=1),), 'allocate real conditional')
        actual = await capture(a, 'actual conditional counter two')
        checker.compare(2, mbtb_counter_for_position(actual, 6), field='initial_MainBTB_counter')
        await train(actual, (BpuBranchFeedback(6, b, 1, taken=0, mispredict=1),), 'prepare actual final not-taken')
        actual = await capture(a, 'actual conditional counter one')
        checker.compare(1, mbtb_counter_for_position(actual, 6), field='negative_MainBTB_counter')
        await train(actual, (BpuBranchFeedback(6, b, 1, taken=0, mispredict=0),), 'prepare low not-taken counter')
        actual = await capture(a, 'actual conditional counter zero with no fallback')
        checker.compare(0, mbtb_counter_for_position(actual, 6), field='actual_initial_NT_counter')
        checker.compare(1, mbtb_meta_for_position(actual, 6)[1]['attribute']['branchType'], field='actual_conditional_resident_without_fallback')
        final_checked(selected_program(intent, alias, 0), actual)
    active_alias = None

    async def steer(alias, goal):
        nonlocal active_alias
        conditional, *_ = programs(intent, alias)
        a, b = (conditional['pc'], conditional['target'])
        if active_alias != alias:
            await drain('move to the next alias')
            if alias % 2 == 0:
                await wait(agent.configure_predictors(abtb=False, settle=True), 'isolate new alias direction preparation', 32)
                actual = await recover(a, checkpoints[a], 'new alias actual metadata before first ABTB recurrence', resume=True)
                for number in range(3):
                    before = mbtb_counter_for_position(actual, 6)
                    if before == 3:
                        break
                    await train(actual, (BpuBranchFeedback(6, b, 1, taken=1, mispredict=int(before < 2)),), 'real pre-residency direction feedback')
                    actual = await capture(a, 'new alias actual direction after feedback')
                    checker.compare(before + 1, mbtb_counter_for_position(actual, 6), field='real_pre_residency_counter_step', step=number)
                checker.compare(3, mbtb_counter_for_position(actual, 6), field='conditional_allocates_before_fallback_on_alternating_aliases')
            await wait(agent.configure_predictors(abtb=True, settle=True), 'enable real ABTB recurrence', 32)
            if alias % 2 == 0:
                actual = await wait(agent.next_transaction(start_pc=a, after_tick=checker.records[-1]['tick'], limit=512), 'fresh admitted conditional without a second recovery', 1024)
            else:
                actual = await recover(a, checkpoints[a], 'start resident pair recurrence', resume=True)
            active_alias = alias
        else:
            await wait(agent.set_ready(prediction=True, meta=True), 'resume resident pair recurrence', 8)
            actual = await wait(agent.next_transaction(start_pc=a, after_tick=checker.records[-1]['tick'], limit=512), 'fresh resident conditional metadata without redirect', 1024)
        for number in range(8):
            counter = mbtb_counter_for_position(actual, 6)
            if counter == goal:
                break
            taken = int(counter < goal)
            branch = BpuBranchFeedback(6, b, 1, taken=taken, mispredict=int((counter >= 2) != bool(taken)))
            transaction = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve, (branch,))
            checker.plan_feedback(transaction)
            accepted = await wait(agent.train_batches_with_prediction_pause((transaction,)), 'accepted real direction feedback preserves ABTB residency', 256)
            report.setdefault('feedback', []).append(dict(phase=checker.phase, transaction=asdict(transaction)))
            actual = await wait(agent.next_transaction(start_pc=a, after_tick=accepted[-1], limit=512), 'new monitored conditional after feedback without redirect', 1024)
            checker.compare(min(3, counter + 1) if taken else max(0, counter - 1), mbtb_counter_for_position(actual, 6), field='actual_MainBTB_counter_step', step=number)
        checker.compare(goal, mbtb_counter_for_position(actual, 6), field='actual_MainBTB_direction_goal')
        final_checked(selected_program(intent, alias, goal), actual)
        return actual
    try:
        await observation.__aenter__()
        pcs = sorted({program['pc'] for alias in range(5) for program in programs(intent, alias)})
        routes = [checkpoint_route(pc) for pc in pcs]
        leads = sorted({route['cold_lead'] for route in routes})
        await wait(agent.reset(leads[0]), 'reset before independent passive references')
        cold = {lead: await wait(agent.next_transaction(start_pc=lead, limit=8192), 'actual cold predecessor checkpoint', 16384) for lead in leads}
        report['cold_sources'] = [asdict(cold[lead]) for lead in leads]
        await wait(agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False, sc=False, ittage=False, ras=False, settle=True), 'isolate MainBTB setup', 32)
        for route in routes:
            checkpoint = cold[route['cold_lead']]
            for target in route['actual_not_taken_checkpoint_targets']:
                checkpoint = await recover(target, checkpoint, 'actual same-halfblock checkpoint hop')
            checkpoints[route['pc']] = checkpoint
        report['checkpoint_routes'] = routes
        report['source_checkpoints'] = [asdict(checkpoints[pc]) for pc in pcs]
        for alias in range(5):
            await prepare(alias)
        for alias in range(5):
            for program in programs(intent, alias):
                checker.phase = 'confirm_all_residents_after_setup'
                actual = await capture(program['pc'], 'complete real MainBTB program residency')
                entry = mbtb_meta_for_position(actual, program['position'])[1]
                checker.compare(program['branch_type'], entry['attribute']['branchType'], field='complete_program_resident')
                expected = selected_program(intent, alias, 0) if program['branch_type'] == 1 else program
                final_checked(expected, actual)
                report.setdefault('all_residents_after_setup', []).append(dict(program=program, source=asdict(actual)))
        for alias in range(5):
            for phase, goal, required in PHASES:
                checker.phase = f'alias{alias}_{phase}'
                await steer(alias, goal)
                begin = checker.bypass.last_event.tick
                for _ in range(2):
                    await wait(observation.settle(32), 'natural pair recurrence without redirects', 128)
                    await wait(agent.pause_prediction_reads(), 'commit real pending SRAM writes', 32)
                end = checker.bypass.last_event.tick
                rises = checker.rises_by_tick
                frames = checker.frames_by_tick
                qualified, witnesses = ([], [])
                program = selected_program(intent, alias, goal)
                for source in checker.coherent_transactions:
                    tick = source['prediction_tick']
                    if not begin < tick <= end or source['meta_tick'] > end:
                        continue
                    token = checker.index_tokens[tick]
                    redirect = frames[tick - 1]['value']['hash_inputs']['redirect_valid']
                    if not input_qualified(source, token, intent, redirect, alias=alias):
                        continue
                    final_checked(program, source)
                    captured = dict(source=deepcopy(source), independent_ABTB_index_token=deepcopy(token), source_ABTB=deepcopy(rises[tick]['abtb']['meta1']), no_actual_provider_output_filter=True)
                    qualified.append(captured)
                    ways = conditional_source_ways(captured['source_ABTB'], 6)
                    if ways:
                        witnesses.append(dict(prediction_tick=tick, actual_conditional_ways=ways))
                checker.compare(True, len(qualified) >= 2, field='actual_intended_bank_set_inputs', alias=alias, direction_phase=phase, count=len(qualified))
                checker.compare(True, len(witnesses) >= 2, field='actual_conditional_entry_survives_direction', alias=alias, direction_phase=phase, count=len(witnesses))
                await drain('confirm phase delayed updates')
                operations = required_operations(checker.confirmed, intent, alias, checker.phase, required)
                checker.compare(True, all(operations.values()), field='all_required_real_counter_transitions', alias=alias, direction_phase=phase, counts={name: len(rows) for name, rows in operations.items()})
                conditional, *_ = programs(intent, alias)
                a, b = (conditional['pc'], conditional['target'])
                expected_entry = dict(valid=1, tag=a & (1 << 24) - 1, position=6, branch_type=1, ras_action=0, target_low=b & (1 << 22) - 1)
                reads = matching_sram_readbacks(observation.write_checks.records, bank=bank, entry_set=entry_set, expected_entry=expected_entry, begin_tick=begin, end_tick=end)
                checker.compare(True, bool(reads), field='complete_conditional_payload_readback_each_phase', alias=alias, direction_phase=phase)
                report.setdefault('alias_windows', []).append(dict(alias=alias, phase=checker.phase, goal=goal, begin_tick=begin, end_tick=end, actual_input_qualified_sources=qualified, actual_conditional_entry_witnesses=witnesses, actual_confirmed_target_operations=operations, actual_SRAM_readbacks=reads))
            report['aliases_executed'] += 1
        checker.compare(True, checker.bypass.nonzero_hash_frames > 0, field='actual_nonzero_history_observed')
        checker.compare(0, len(checker.feedback_plans), field='all_submitted_feedback_observed')
        direct = observation.write_checks.summary()
        checker.compare(len(checker.bypass.records), direct['frames'], field='complete_direct_ABTB_observations')
        checker.compare(525, len(observation.write_monitor.signal_paths), field='all_memory_direct_leaves_bound')
        report.update(passed=True, direct_ABTB_summary=direct, ABTB_summary=checker.summary(), bypass_summary=checker.bypass.finish(), direct_ABTB_signal_paths=list(observation.write_monitor.signal_paths))
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records, preedge_records=checker.control_records, coherent_transactions=checker.coherent_transactions, feedback_accepts=checker.feedback_accepts, accepts=checker.accepts, confirmed_transitions=checker.confirmed, gates=checker.gates, ABTB_index_records=checker.index_records, direct_ABTB_records=observation.write_checks.records, direct_ABTB_confirmed_actions=observation.write_checks.confirmed_actions, direct_ABTB_failed_frame=observation.write_checks.failed_frame, bypass_records=checker.bypass.records, bypass_writes=checker.bypass.writes, bank_writes=checker.bypass.bank_writes, SRAM_reads=checker.bypass.SRAM_reads, forced_conflicts=checker.bypass.forced_conflicts, reset_cache_divergences=checker.bypass.reset_cache_divergences, failed_frame=checker.bypass.failed_frame)
        target = output / f'integrated-later-taken-cycle-bank{bank}-set{entry_set}.json.gz'
        dump_trace(target, report)
    return report
