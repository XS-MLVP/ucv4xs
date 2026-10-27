"""bpuverify.bpu.case.sc.role_scenarios components."""

from collections import Counter
from dataclasses import asdict
from dataclasses import fields
from bpuverify.common.env.trace import dump_trace
from itertools import combinations
from bpuverify.bpu.model.sc.provider_roles import PROFILES
from bpuverify.bpu.model.sc.provider_roles import selectors
from bpuverify.bpu.model.sc.provider_roles import next_feedback
from bpuverify.bpu.model.sc.provider_roles import validate_transition
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.env.phr.observation import BpuPhrObservation
from bpuverify.bpu.checker.sc.checker import ScChecker
from bpuverify.bpu.monitor.sc.observer import ScMonitor
from bpuverify.bpu.case.sc.scenarios import bounded
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.model.sc.metadata import sc_decisions_for_positions
from bpuverify.bpu.model.sc.metadata import tage_meta_for_position
from bpuverify.bpu.model.sc.metadata import tage_provider_signatures
from bpuverify.bpu.checker.sc.role_scenarios import CombinedChecks
from bpuverify.bpu.checker.sc.role_scenarios import ZeroHistoryChecker


def neutral_target(pc, position):
    branch_pc = (pc & ~7) + position
    target = (pc & ~0xffff) + 0x10000 + ((branch_pc & 511) << 5)
    assert path_hash(branch_pc, target) == 0
    return target


def source_pc(pc):
    return pc - 1 if pc & 1 else pc - 8


async def revisit(agent, phr, pc, checkpoint):
    assert checkpoint.prediction.start_pc == source_pc(pc)
    assert ((pc - 1) & ~7) == (checkpoint.prediction.start_pc & ~7)
    recovery = BpuRedirect(pc, checkpoint.meta.redirect, cfi_pc=pc - 1, taken=0, branch_type=1)
    boundary = await agent.redirect(recovery)
    return await agent.next_transaction(start_pc=pc, after_tick=boundary)


async def prepare_pair(agent, phr, pc, checkpoint, positions, goals, *, targets=None):
    earlier, later = positions
    if targets is None:
        targets = tuple(neutral_target(pc, position) for position in positions)
    if len(targets) != 2 or any(type(value) is not int or not 0 <= value < 1 << 49 for value in targets):
        raise ValueError('provider pair requires two unsigned halfword targets')
    first_target, second_target = targets
    await agent.configure_predictors(ubtb=False, abtb=False, tage=True, sc=False,
                                    ittage=False, ras=False, settle=True)
    cold = await revisit(agent, phr, pc, checkpoint)
    assert cold.prediction.taken == 0
    await agent.train(BpuTraining(pc, earlier, first_target, cold.meta.resolve, branch_type=1))
    first = await revisit(agent, phr, pc, checkpoint)
    assert mbtb_counter_for_position(first, earlier) == 2
    await agent.train_batch(BpuBatchTraining(pc, first.meta.resolve, (
        BpuBranchFeedback(earlier, first_target, 1, taken=0), None,
        BpuBranchFeedback(later, second_target, 1, taken=1, mispredict=1))))
    residents = await revisit(agent, phr, pc, checkpoint)
    assert (mbtb_counter_for_position(residents, earlier), mbtb_counter_for_position(residents, later)) == (1, 2)
    assert not tage_meta_for_position(residents, earlier)['hasProvider']
    assert not tage_meta_for_position(residents, later)['hasProvider']
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(pc, residents.meta.resolve,
        (BpuBranchFeedback(earlier, first_target, 1, taken=1, mispredict=1),)))
    single = await revisit(agent, phr, pc, checkpoint)
    assert tage_meta_for_position(single, earlier)['providerTakenCtr_value'] == 4
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(pc, single.meta.resolve,
        (BpuBranchFeedback(earlier, first_target, 1, taken=0, mispredict=1),)))
    negative = await revisit(agent, phr, pc, checkpoint)
    assert tage_meta_for_position(negative, earlier)['providerTakenCtr_value'] == 3
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(pc, negative.meta.resolve, (
        BpuBranchFeedback(earlier, first_target, 1, taken=0), None,
        BpuBranchFeedback(later, second_target, 1, taken=0, mispredict=1))))
    both = await revisit(agent, phr, pc, checkpoint)
    providers = tage_provider_signatures(both, positions)
    assert providers[0][:2] != providers[1][:2]
    assert tuple(item[2] for item in providers) == (2, 3)
    preparation_steps = []
    for step in range(16):
        prior = tage_provider_signatures(both, positions)
        selection = next_feedback(tuple(item[2] for item in prior), goals)
        if selection is None:
            break
        lane, taken = selection
        position, target = positions[lane], (first_target, second_target)[lane]
        feedbacks = [None, None, None]
        meta = tage_meta_for_position(both, position)
        predicted = int(meta['providerTakenCtr_value'] >= 4) if meta['useProvider'] else meta['altOrBasePred']
        feedback = BpuBranchFeedback(position, target, 1, taken=taken, mispredict=int(predicted != taken))
        feedbacks[lane * 2] = feedback
        transaction = BpuBatchTraining(pc, both.meta.resolve, tuple(feedbacks))
        before_step = both
        await agent.train_batch_with_prediction_pause(transaction)
        both = await revisit(agent, phr, pc, checkpoint)
        current = tage_provider_signatures(both, positions)
        action = validate_transition(prior, current, lane=lane, taken=taken, mispredict=feedback.mispredict)
        preparation_steps.append(dict(step=step, lane=lane, taken=taken, action=action,
            before=asdict(before_step), transaction=asdict(transaction), after=asdict(both)))
    else:
        raise AssertionError(dict(operation='bounded real provider role preparation', pc=pc,
            expected_counters=goals, actual=tage_provider_signatures(both, positions)))
    await agent.configure_predictors(sc=True, settle=True)
    qualified = await revisit(agent, phr, pc, checkpoint)
    assert tuple(item[2] for item in tage_provider_signatures(qualified, positions)) == tuple(goals)
    actual_selectors = tuple(qualified.meta.resolve['sc']['scBiasLowerBits'][
        mbtb_meta_for_position(qualified, position)[0]] for position in positions)
    assert actual_selectors == selectors(goals), dict(field='captured_bias_selectors',
        expected=selectors(goals), actual=actual_selectors)
    assert sc_decisions_for_positions(qualified, positions) == ((1, 0, 0), (1, 0, 0))
    assert qualified.meta.resolve['commonHR']['valid'] == 0
    return cold, qualified, preparation_steps


def status(scoreboard):
    return {field.name: repr(value) if field.name == 'first_failure' and value is not None else value
            for field in fields(scoreboard.status) for value in (getattr(scoreboard.status, field.name),)}


async def run_depth(agent, execution, output, case):
    bank, positions = case['bank'], tuple(case['positions'])
    goals = PROFILES[case['provider_profile']]
    assert bank in (0, 1) and positions in tuple(combinations((4, 5, 6, 7), 2))
    assert case['key_order'] in ('forward', 'reverse') and case['mask_order'] in ('forward', 'reverse')
    sc = ScChecker(case, capacity=8192)
    phr = ZeroHistoryChecker(scope='SC four-key full-zero-history diagnostic')
    checks = CombinedChecks(sc, phr)
    phr_observation = BpuPhrObservation(agent, phr)
    await phr_observation.__aenter__()
    sc_monitor = ScMonitor(agent)
    sc_monitor.start(execution, observer=sc.capture, controls=sc.capture_controls)
    report = dict(case=case, formal_credit=False, native_credit=False,
        complete_FTQ_legality_proven=False, prediction_overlap_claimed=False,
        hardware_internal_state_written=False, coherent_transaction_observation=True,
        source_checkpoints=[], captured=[], phases=[])

    async def wait(operation, label, cycles=8192):
        return await bounded(agent.dut.clock, operation, cycles=cycles, checker=checks, label=label)

    try:
        pcs = [0x40004000 + key * 0x80 + bank for key in range(4)]
        leads = [source_pc(pc) - (8 if bank == 0 else 0) for pc in pcs]
        await wait(agent.reset(leads[0]), 'actual reset before cold checkpoint capture')
        checkpoints = []
        for lead in leads:
            checkpoint = await wait(agent.next_transaction(start_pc=lead), 'capture genuine aligned zero-history source transaction')
            assert checkpoint.prediction.taken == 0
            assert checkpoint.meta.redirect['phr']['phrLowBits'] == 0
            checkpoints.append(checkpoint)
        if bank == 0:
            checkpoints = [await wait(revisit(agent, phr, source_pc(pc), checkpoint),
                'capture genuine half-block checkpoint through not-taken recovery')
                for pc, checkpoint in zip(pcs, checkpoints, strict=True)]
        for checkpoint in checkpoints:
            report['source_checkpoints'].append(asdict(checkpoint))
        captures = []
        for pc, checkpoint in zip(pcs, checkpoints, strict=True):
            cold, before, preparation_steps = await wait(prepare_pair(agent, phr, pc, checkpoint, positions, goals), 'prepare genuine pair without history pollution')
            item = dict(pc=pc, checkpoint=checkpoint, cold=cold, before=before,
                providers=tage_provider_signatures(before, positions),
                targets=[neutral_target(pc, position) for position in positions])
            captures.append(item)
            report['captured'].append(dict(pc=pc, cold=asdict(cold), before=asdict(before), targets=item['targets'], preparation_steps=preparation_steps))
        for field in ('predPathIdx', 'predImliIdx', 'predBiasIdx'):
            indices = [item['before'].meta.resolve['sc']['debug'][field] for item in captures]
            if field == 'predPathIdx':
                indices = [value[0] for value in indices]
            sc.check(4, len(set(indices)), field='four_real_distinct_SC_keys', index_kind=field, indices=indices)
        if case['key_order'] == 'reverse':
            captures.reverse()
        mask_lanes = (0, 1) if case['mask_order'] == 'forward' else (1, 0)
        await wait(agent.configure_predictors(tage=False, settle=True), 'hold all four provider pairs', cycles=32)
        for iteration in range(2):
            transactions = tuple(BpuBatchTraining(item['pc'], item['before'].meta.resolve,
                (BpuBranchFeedback(positions[0], item['targets'][0], 1, taken=0), None, None) if lane == 0 else
                (None, None, BpuBranchFeedback(positions[1], item['targets'][1], 1, taken=0)))
                for lane in mask_lanes for item in captures)
            sc.phase = f'drive_{iteration}'
            sc.plan(transactions)
            ticks = await wait(agent.train_batches_with_prediction_pause(transactions), 'eight adjacent distinct-key feedbacks', cycles=256)
            sc.check([2] * 7, [b - a for a, b in zip(ticks, ticks[1:])], field='all_eight_hardware_accepts_adjacent')
            sc.check(list(ticks), [row['tick'] for row in sc.accepts if row['phase'] == sc.phase],
                     field='all_eight_driver_monitor_accepts_aligned')
            sc.phase = f'drain_{iteration}'
            await wait(agent.pause_prediction_reads(), 'drain all four SC keys', cycles=32)
            await wait(agent.configure_predictors(tage=True, settle=True), 'enable full public provider readback', cycles=32)
            sc.phase = f'readback_{iteration}'
            readbacks = []
            for item in captures:
                actual = await wait(revisit(agent, phr, item['pc'], item['checkpoint']), 'read back both positions for each key', cycles=256)
                sc.check(item['providers'], tage_provider_signatures(actual, positions), field='all_eight_original_providers_retained', pc=item['pc'])
                sc.check(((0, 0, 0), (0, 0, 0)), sc_decisions_for_positions(actual, positions),
                         field='both_SC_directions_for_each_key', pc=item['pc'])
                sc.check(0, actual.meta.resolve['commonHR']['valid'], field='readback_retains_commonHR_invalid_scope')
                item['before'] = actual
                readbacks.append(asdict(actual))
            report['phases'].append(dict(transactions=[asdict(tx) for tx in transactions], training_ticks=list(ticks), readbacks=readbacks))
            if iteration == 0:
                await wait(agent.configure_predictors(tage=False, settle=True), 'hold providers for clean-key reactivation', cycles=32)
        witnesses = []
        for row in sc.records:
            if not row['phase'].startswith('drive_'):
                continue
            for name, buffer in row['buffers'].items():
                if not buffer['write']['valid']:
                    continue
                for slot, entry in enumerate(buffer['slots']):
                    if entry['valid'] and entry['payload']['set_index'] == buffer['write']['bits']['set_index']:
                        witnesses.append(dict(tick=row['tick'], phase=row['phase'], buffer=name, slot=slot,
                            kind='dirty_merge' if entry['dirty'] else 'clean_reactivate'))
        for table in ('pathTable_0', 'imliTable', 'biasTable'):
            for kind in ('dirty_merge', 'clean_reactivate'):
                sc.check({0, 1, 2, 3}, {row['slot'] for row in witnesses
                    if row['buffer'] == f'{table}_bank{bank}' and row['kind'] == kind},
                    field='all_four_actual_shadow_depths', table=table, kind=kind)
        report.update(passed=True, witnesses=witnesses, summary=sc.summary(), phr_summary=phr.summary(),
            action_counts=dict(Counter(row['kind'] for row in sc.actions)))
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await sc_monitor.aclose()
        await phr_observation.aclose(resume_streams=False)
        report.update(records=sc.records, preedge_records=sc.control_records, phr_records=phr.records,
            accepts=sc.accepts, actions=sc.actions, drains=sc.drains,
            sc_scoreboard_status=status(sc.scoreboard), phr_scoreboard_status=status(phr.scoreboard))
        dump_trace((output / f'sc-provider-role-{identity(case)}.json'), report, default=str)

    return report


def identity(case):
    return (f"bank{case['bank']}-pair{case['positions'][0]}_{case['positions'][1]}-"
            f"keys_{case['key_order']}-masks_{case['mask_order']}-{case['provider_profile']}")
