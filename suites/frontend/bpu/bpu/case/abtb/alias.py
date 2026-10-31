"""Real driver feedback and parallel passive monitors; no test pin scheduling."""
from copy import deepcopy
from dataclasses import asdict
from suites.frontend.bpu.runtime.trace import dump_trace
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_meta_for_position
from suites.frontend.bpu.bpu.case.abtb.timeouts import bounded
from suites.frontend.bpu.bpu.case.bypass.public_readback import conditional_source_ways
from suites.frontend.bpu.bpu.checker.abtb.stream import PairChecks
from suites.frontend.bpu.bpu.checker.abtb.stream import PairObservation
from suites.frontend.bpu.bpu.case.abtb.readback import matching_sram_readbacks
from suites.frontend.bpu.bpu.case.abtb.alias_plan import checkpoint_route
from suites.frontend.bpu.bpu.case.abtb.alias_plan import final_comparison
from suites.frontend.bpu.bpu.case.abtb.alias_plan import input_qualified
from suites.frontend.bpu.bpu.model.abtb.alias import plan
from suites.frontend.bpu.bpu.case.abtb.alias_plan import programs


async def run_five_alias_cycle(agent, output, *, bank, entry_set, coverage=None):
    intent = plan(bank, entry_set)
    checker = PairChecks(dict(bank=bank, entry_set=entry_set, scope='native five-alias same-bank/set four-way replacement'), coverage=coverage)
    observation = PairObservation(agent, checker)
    report = dict(plan=intent, passed=False, aliases_executed=0,
        direct_ABTB_observation_required=True,
        committed_internal_reset_used_not_pending_public_RiseWrite_cache=True,
        only_one_of_five_planned_alias_pairs_executed=False,
        all_five_alias_pairs_required=True, all256_groups_executed=False,
        SRAM_readback_association='preedge request to next rising response; both inside alias window',
        hardware_internal_state_written=False, metadata_fabricated=False,
        full_FTQ_legality_proven=False, full_ABTB_SRAM_write_generation_claimed=False,
        all256_groups_claimed=False,
        native_credit=False, formal_credit=False)
    checkpoints = {}

    async def wait(operation, label, cycles=8192):
        return await bounded(agent, checker, operation, label, cycles)

    async def recover(target, checkpoint, label):
        source = checkpoint.prediction.start_pc
        checker.compare((target - 1) & ~15, source & ~15, field='actual_same_halfblock_checkpoint')
        checker.compare(True, source <= target - 1, field='checkpoint_precedes_CFI')
        transaction = BpuRedirect(target, checkpoint.meta.redirect,
            cfi_pc=target - 1, taken=0, branch_type=1)
        report.setdefault('recoveries', []).append(dict(payload=transaction.payload(), source=asdict(checkpoint)))
        accepted = await wait(agent.redirect(transaction), label + ': actual redirect', 32)
        actual = await wait(agent.next_transaction(start_pc=target, after_tick=accepted, limit=512), label, 1024)
        report.setdefault('public_captures', []).append(dict(phase=checker.phase, **asdict(actual)))
        return actual

    async def capture(pc, label):
        return await recover(pc, checkpoints[pc], label)

    async def train(actual, program):
        transaction = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve,
            (BpuBranchFeedback(program['position'], program['target'], program['branch_type'],
                taken=1, mispredict=1),))
        checker.plan_feedback(transaction)
        await wait(agent.train_batch_with_prediction_pause(transaction), 'real pair branch allocation', 256)
        report.setdefault('feedback', []).append(dict(phase=checker.phase, transaction=asdict(transaction)))

    def final_checked(program, actual):
        source = actual if isinstance(actual, dict) else asdict(actual)
        rows = [row for row in checker.records if row['tick'] == source['meta_tick']]
        checker.compare(1, len(rows), field='exact_associated_S3_event_exists')
        expected, observed = final_comparison(program, source, rows[0])
        checker.compare(expected, observed, field='real_pair_final_S3_edge',
            source=source, exact_meta_tick=source['meta_tick'])
        return observed

    try:
        await observation.__aenter__()
        branches = [program for alias in range(5) for program in programs(intent, alias)]
        routes = [checkpoint_route(program['pc']) for program in branches]
        leads = sorted({route['cold_lead'] for route in routes})
        await wait(agent.reset(leads[0]), 'reset before every passive reference')
        cold = {lead: await wait(agent.next_transaction(start_pc=lead, limit=8192),
            'actual cold predecessor checkpoint', 16384) for lead in leads}
        report['cold_sources'] = [asdict(cold[lead]) for lead in leads]
        await wait(agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True), 'isolate actual MainBTB setup', 32)
        for route in routes:
            checkpoint = cold[route['cold_lead']]
            for target in route['actual_not_taken_checkpoint_targets']:
                checkpoint = await recover(target, checkpoint, 'actual checkpoint hop')
            checkpoints[route['pc']] = checkpoint
        report['checkpoint_routes'] = routes
        report['source_checkpoints'] = [asdict(checkpoints[row['pc']]) for row in branches]
        for program in branches:
            checker.phase = f'prepare_{program["pc"]:x}'
            actual = await capture(program['pc'], 'genuine cold branch source')
            await train(actual, program)
            actual = await capture(program['pc'], 'actual learned branch readback')
            entry = mbtb_meta_for_position(actual, 7)[1]
            checker.compare(program['branch_type'], entry['attribute']['branchType'], field='MainBTB_branch_resident')
            report.setdefault('branch_residents', []).append(dict(program=program, source=asdict(actual)))
        for program in branches:
            checker.phase = 'confirm_both_residents_after_allocation'
            actual = await capture(program['pc'], 'complete pair residency')
            entry = mbtb_meta_for_position(actual, 7)[1]
            checker.compare(program['branch_type'], entry['attribute']['branchType'], field='pair_still_resident')
            report.setdefault('all_residents_after_setup', []).append(dict(program=program,
                source=asdict(actual), associated_final_S3=final_checked(program, actual)))
        await wait(agent.configure_predictors(abtb=True, settle=True), 'enable actual ABTB/UTAGE learning', 32)
        for alias in range(5):
            checker.phase = f'natural_positive_pair_alias{alias}'
            pair_branches = programs(intent, alias)
            await wait(agent.set_ready(prediction=True, meta=True), 'resume next real alias stream', 8)
            a, b = intent['taken_pairs'][alias]
            await capture(a, 'start genuine positive pair recurrence')
            begin = checker.bypass.last_event.tick
            for _ in range(4):
                await wait(observation.settle(64), 'natural taken pair without redirects', 128)
                await wait(agent.pause_prediction_reads(), 'drain actual pending SRAM writes', 32)
            end = checker.bypass.last_event.tick
            rises = checker.rises_by_tick
            frames = checker.frames_by_tick
            qualified, entry_witnesses = [], []
            for source in checker.coherent_transactions:
                tick = source['prediction_tick']
                if not begin < tick <= end:
                    continue
                token = checker.index_tokens[tick]
                redirect = frames[tick - 1]['value']['hash_inputs']['redirect_valid']
                if not input_qualified(source, token, intent, redirect, alias=alias):
                    continue
                # Input qualification does not inspect conditional hit/provider outputs.
                final_checked(pair_branches[1], source)
                captured = dict(source=deepcopy(source), independent_ABTB_index_token=deepcopy(token),
                    source_ABTB=deepcopy(rises[tick]['abtb']['meta1']), no_actual_provider_output_filter=True)
                qualified.append(captured)
                ways = conditional_source_ways(captured['source_ABTB'], 7)
                if ways:
                    entry_witnesses.append(dict(prediction_tick=tick, actual_conditional_ways=ways,
                        independent_ABTB_index_token=deepcopy(token)))
            checker.compare(True, len(qualified) >= 2, field='real_intended_bank_set_inputs',
                qualified=len(qualified), requested_bank=bank, requested_set=entry_set)
            checker.compare(True, len(entry_witnesses) >= 2, field='conditional_ABTB_entry_actually_primed',
                count=len(entry_witnesses))
            for program in pair_branches:
                edges = [row for row in checker.control_records if begin < row['tick'] <= end
                    and row['abtb']['fast']['valid'] and row['abtb']['fast']['pc'] == program['pc']
                    and row['abtb']['fast']['target'] == program['target'] and row['abtb']['fast']['taken']
                    and row['abtb']['fast']['position'] == 7 and row['abtb']['fast']['branch_type'] == program['branch_type']]
                checker.compare(True, len(edges) >= 2, field='both_intended_S3_pair_edges_observed', program=program)
            await wait(agent.set_ready(prediction=False, meta=True), 'stop younger prediction tasks', 8)
            await wait(observation.drain(), 'confirm all delayed updates', 32)
            checker.compare((None, None), (checker.counter.pending1, checker.counter.pending2), field='all_ABTB_tasks_drained')
            operations = {name: [row for row in checker.confirmed if row['phase'] == checker.phase
                and row['bank'] == bank and row['set_index'] == entry_set and row['transition'] == name
                and row['feedback'] is not None and row['feedback']['pc'] == a] for name in ('inc2_3', 'inc3_3')}
            checker.compare(True, all(operations.values()), field='real_conditional_increment_and_high_saturation',
                actual_counts={key: len(value) for key, value in operations.items()})
            # All port samples were compared against reset/input-derived
            # expectations. The selection below only proves that this alias
            # was actually visible on an SRAM read; it never seeds the model.
            program = pair_branches[1]
            expected_entry = dict(valid=1, tag=a & ((1 << 24) - 1), position=7,
                branch_type=1, ras_action=0, target_low=b & ((1 << 22) - 1))
            readbacks = matching_sram_readbacks(observation.write_checks.records,
                bank=bank, entry_set=entry_set, expected_entry=expected_entry,
                begin_tick=begin, end_tick=end)
            checker.compare(True, bool(readbacks), field='complete_alias_payload_visible_in_real_SRAM_read',
                alias=alias, expected_entry=expected_entry)
            report.setdefault('alias_windows', []).append(dict(alias=alias, phase=checker.phase,
                begin_tick=begin, end_tick=end, actual_input_qualified_sources=qualified,
                actual_conditional_entry_witnesses=entry_witnesses,
                actual_confirmed_target_operations=operations, actual_SRAM_readbacks=readbacks))
            report['aliases_executed'] += 1
        allocations = [row for row in observation.write_checks.confirmed_actions
            if row['bank'] == bank and row['request_role'] == 'allocate'
            and row['payload']['set_index'] == entry_set]
        alias_allocations = []
        for alias, (a, b) in enumerate(intent['taken_pairs']):
            tag = a & ((1 << 24) - 1)
            rows = [row for row in allocations if row['payload']['tag'] == tag]
            checker.compare(True, bool(rows), field='each_of_five_aliases_has_confirmed_real_allocation',
                alias=alias, bank=bank, entry_set=entry_set)
            wanted = dict(need_reset=1, set_index=entry_set, valid=1, tag=tag,
                position=7, branch_type=1, ras_action=0, target_low=b & ((1 << 22) - 1))
            for row in rows:
                checker.compare(wanted, {name: row['payload'][name] for name in wanted},
                    field='confirmed_alias_allocation_complete_payload', alias=alias)
            alias_allocations.extend(dict(alias=alias, **deepcopy(row)) for row in rows)
        ways = {row['payload']['way'] for row in alias_allocations}
        checker.compare(set(range(4)), ways, field='all_four_real_SRAM_allocation_ways')
        tags_by_way = {way: sorted({row['payload']['tag'] for row in alias_allocations
            if row['payload']['way'] == way}) for way in ways}
        checker.compare(True, any(len(tags) >= 2 for tags in tags_by_way.values()),
            field='fifth_distinct_alias_replaces_a_previously_allocated_way')
        report.update(actual_five_alias_allocation_actions=alias_allocations,
            actual_tags_by_reused_way=tags_by_way, four_way_allocation_and_reuse_checked=True,
            dirty_full_overwrite_claimed=False)
        checker.compare(True, checker.bypass.nonzero_hash_frames > 0, field='actual_nonzero_history_used')
        checker.compare(0, len(checker.feedback_plans), field='all_submitted_feedback_observed')
        direct = observation.write_checks.summary()
        checker.compare(len(checker.bypass.records), direct['frames'], field='all_parent_events_have_direct_ABTB_observation')
        checker.compare(525, len(observation.write_monitor.signal_paths), field='all_direct_ABTB_memory_direct_leaves_bound')
        report['direct_ABTB_signal_paths'] = list(observation.write_monitor.signal_paths)
        report.update(passed=True, direct_ABTB_summary=direct,
            ABTB_summary=checker.summary(),
            bypass_summary=checker.bypass.finish())
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records, preedge_records=checker.control_records,
            coherent_transactions=checker.coherent_transactions, feedback_accepts=checker.feedback_accepts,
            accepts=checker.accepts, confirmed_transitions=checker.confirmed, gates=checker.gates,
            ABTB_index_records=checker.index_records,
            direct_ABTB_records=observation.write_checks.records,
            direct_ABTB_confirmed_actions=observation.write_checks.confirmed_actions,
            direct_ABTB_failed_frame=observation.write_checks.failed_frame,
            bypass_records=checker.bypass.records,
            bypass_writes=checker.bypass.writes, bank_writes=checker.bypass.bank_writes,
            SRAM_reads=checker.bypass.SRAM_reads, forced_conflicts=checker.bypass.forced_conflicts,
            reset_cache_divergences=checker.bypass.reset_cache_divergences, failed_frame=checker.bypass.failed_frame)
        target = output / f'integrated-five-alias-bank{bank}-set{entry_set}.json.gz'
        dump_trace(target, report)
    return report
