"""Normal-driver dual writes with frozen input/state references and full readback.

This qualifies the standalone TAGE feedback contract, not integrated FTQ
reachability. Metadata comes from one genuine NT/T prediction; no native signal
is written and no observed post-write state supplies an expected transition.
"""
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode

from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.transaction.types import TageLookup
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.coverage.dual import DUAL_MODES
from bpuverify.tage.model.dual_shadow import advance_tage_shadow_writes
from bpuverify.tage.driver.feedback import expected_tage_feedback
from bpuverify.tage.driver.feedback import observed_tage_feedback
from tests.tage.diagnostics.retained_owner_probe import initial_shadows
from tests.tage.diagnostics.retained_owner_probe import read_profiles
from bpuverify.tage.checker.assertions import fill_useful_set
from bpuverify.tage.case.way_migration_scenario import cell
from bpuverify.tage.case.way_migration_scenario import prepare_unprotected_highest_ways
from bpuverify.tage.case.way_migration_scenario import snapshot


def validate_case(bank, depth, mode):
    if bank not in range(4) or depth not in range(4) or mode not in DUAL_MODES:
        raise ValueError('unsupported TAGE dual-shadow bank/depth/mode')


async def set_counter(agent, pc, position, wanted, owner):
    for _ in range(8):
        prediction = await agent.predict(pc, position, int(wanted >= 4))
        assert cell(prediction) == (3, owner)
        assert prediction.meta['providerUsefulCtr_value'] == 0
        old = prediction.meta['providerTakenCtr_value']
        if old == wanted:
            return deepcopy(prediction.meta)
        taken = int(old < wanted)
        before = await agent.predict(pc, position, taken)
        final = before.taken if before.valid else taken
        await agent.train(TageTraining(pc, position, taken, taken, before.meta,
            mispredict=int(final != taken)))
    raise AssertionError(('counter did not converge', pc, position, wanted))


async def allocate(agent, pc, position, taken, owner):
    cold = await agent.predict(pc, position, 1 - taken)
    assert not cold.meta['hasProvider']
    await agent.train(TageTraining(pc, position, taken, 1 - taken, cold.meta, mispredict=1))
    after = await agent.predict(pc, position, taken)
    assert cell(after) == (3, owner)
    assert (after.meta['providerTakenCtr_value'], after.meta['providerUsefulCtr_value']) == (
        4 if taken else 3, 0)


async def prepare_case(agent, bank, depth, mode):
    validate_case(bank, depth, mode)
    pc = 0x40000000 + bank
    b = await prepare_unprotected_highest_ways(agent, pc, 1)
    rows = {position: await agent.predict(pc, position, 1) for position in range(9)}
    a = next(position for position, pred in rows.items()
             if pred.meta['hasProvider'] and cell(pred) == (3, 0))
    assert a < b
    await set_counter(agent, pc, a, 2, 0)
    capture = agent.submit_predict_branches(pc, (TageBaseBranch(a, 0), TageBaseBranch(b, 1)))
    prediction = await capture
    assert prediction.valids[:2] == (1, 1) and prediction.takens[:2] == (0, 1)
    ma, mb = deepcopy(prediction.metas[0]), deepcopy(prediction.metas[1])
    for meta, wanted in ((ma, (0, 2, 0, 0)), (mb, (1, 5, 0, 1))):
        assert tuple(meta[name] for name in ('providerWayIdx', 'providerTakenCtr_value',
            'providerUsefulCtr_value', 'altOrBasePred')) == wanted
    cross = mode.startswith('cross_')
    mixed = mode.startswith('companion_')
    if cross:
        await set_counter(agent, pc, b, 4, 1)
        await allocate(agent, pc, 9, 1, 1)
        await set_counter(agent, pc, 9, 7, 1)
        await allocate(agent, pc, b, 1, 0)
        await set_counter(agent, pc, b, 5, 0)
        await set_counter(agent, pc, 9, 4, 1)
        await allocate(agent, pc, a, 0, 1)
        await set_counter(agent, pc, b, 4, 0)
    current_a = deepcopy((await agent.predict(pc, a, 0)).meta)
    current_b = deepcopy((await agent.predict(pc, b, 1)).meta)
    assert (current_a['providerWayIdx'], current_a['providerTakenCtr_value']) == (
        (1, 3) if cross else (0, 2))
    assert (current_b['providerWayIdx'], current_b['providerTakenCtr_value']) == (
        (0, 4) if cross else (1, 5))
    profiles = {pc: {position: deepcopy(snapshot(await agent.predict(pc, position, 1)))
                     for position in range(10)}}
    dummy = []
    for index in range(max(1, depth) if mixed else depth):
        address = pc + 0x20 * (index + 1)
        residents = await fill_useful_set(agent, pc=address)
        profiles[address] = {position: deepcopy(snapshot(await agent.predict(address, position, 1)))
                             for position in range(8)}
        positions = tuple(next(position for position, pred in residents.items()
                               if cell(pred) == (3, owner)) for owner in (0, 1))
        assert all(profiles[address][position]['meta']['providerTakenCtr_value'] == 5
                   for position in positions)
        dummy.append((address, positions))
    preparation = []
    if mode in ('companion_miss', 'companion_miss_saturated'):
        address, positions = dummy[-1]
        for counter in (6, 7):
            before = await agent.predict(address, positions[1], 1)
            await agent.train(TageTraining(address, positions[1], 1, 1, before.meta, mispredict=0))
            wanted = deepcopy(profiles[address][positions[1]])
            wanted['meta']['providerTakenCtr_value'] = counter
            actual = snapshot(await agent.predict(address, positions[1], 1))
            assert actual == wanted
            profiles[address][positions[1]] = wanted
            preparation.append(dict(expected=wanted, actual=deepcopy(actual)))
    address = dummy[-1][0] if dummy else pc
    initial = initial_shadows(address, profiles[address])
    if mode == 'companion_clean_hit':
        await agent.train(TageTraining(pc, b, 1, 1, mb, mispredict=0))
        wanted = deepcopy(profiles[pc][b])
        wanted['meta']['providerTakenCtr_value'] = 6
        actual = snapshot(await agent.predict(pc, b, 1))
        assert actual == wanted
        profiles[pc][b] = wanted
        preparation.append(dict(expected=wanted, actual=deepcopy(actual)))
        initial[bank][1][0].update(valid=1, dirty=0, set_idx=(pc >> 2) & 127,
            tag=((pc >> 9) & 8191) ^ b, entry_valid=1, counter=6)
    expected_profiles, transactions, frames = deepcopy(profiles), [], []

    def append(address, branches, payloads):
        transactions.append(TageBatchTraining(address, tuple(branches)))
        frame = [[None, None] for _ in range(4)]
        for port, position, counter, taken in payloads:
            frame[bank][port] = dict(set_idx=(address >> 2) & 127,
                tag=((address >> 9) & 8191) ^ position, counter=counter, entry_valid=1, taken=taken)
        frames.append(tuple(tuple(row) for row in frame))

    for address, positions in dummy[:depth]:
        owners = (0, 1) if not mixed or mode == 'companion_dirty_hit' else (0,)
        for owner in owners:
            position = positions[owner]
            meta = deepcopy(profiles[address][position]['meta'])
            append(address, (TageBranchFeedback(position, 1, 1, meta),), ((owner, position, 6, 1),))
            expected_profiles[address][position]['meta']['providerTakenCtr_value'] = 6
    if cross:
        append(pc, (TageBranchFeedback(a, 0, 0, current_a),), ((1, a, 2, 0),))
        append(pc, (TageBranchFeedback(b, 1, 1, current_b),), ((0, b, 5, 1),))
    elif not mixed:
        append(pc, (TageBranchFeedback(a, 0, 0, ma), TageBranchFeedback(b, 1, 1, mb)),
               ((0, a, 1, 0), (1, b, 6, 1)))
    elif mode == 'companion_dirty_hit':
        append(pc, (TageBranchFeedback(b, 1, 1, mb),), ((1, b, 6, 1),))
    elif mode in ('companion_miss', 'companion_miss_saturated'):
        for _ in range(2 if mode == 'companion_miss_saturated' else 1):
            append(pc, (TageBranchFeedback(a, 0, 0, ma),), ((0, a, 1, 0),))
    for _ in range(3):
        append(pc, (TageBranchFeedback(a, 0, 0, ma), TageBranchFeedback(b, 1, 1, mb)),
               ((0, a, 1, 0), (1, b, 6, 1)))
    expected_profiles[pc][a].update(valid=1, taken=0, provider_counter_valid=1)
    expected_profiles[pc][a]['meta'].update(providerTakenCtr_value=0, useProvider=1)
    expected_profiles[pc][b]['meta'].update(providerTakenCtr_value=7, useProvider=1)
    return dict(bank=bank, depth=depth, mode=mode, a=a, b=b, initial_shadows=initial,
        transactions=tuple(transactions), expected_writes=tuple(frames),
        expected_inputs=tuple(expected_tage_feedback(tx) for tx in transactions),
        prepared_profiles=profiles, expected_profiles=expected_profiles, preparation_checks=preparation,
        captured_meta=(ma, mb), current_meta=(current_a, current_b),
        captured_prediction=asdict(prediction), capture_tick=capture.completed_event.tick)


def expected_witnesses(bank, depth, mode):
    """Hand-derived first miss/hit and saturation sequences, not model output."""
    validate_case(bank, depth, mode)
    result = []
    own, cross = mode.startswith('own_'), mode.startswith('cross_')
    clean = mode.endswith('_clean')
    for phase in range(4 if own else 3):
        for port in range(2):
            selected_depth = depth
            if cross:
                old = ((2, 1, 0), (5, 6, 7))[port][phase]
                new = ((1, 0, 0), (6, 7, 7))[port][phase]
                hit, dirty, ready = 1, int(not clean), int(clean)
            elif own:
                old = (((2 if depth == 0 else 0), 1, 0, 0),
                       ((5 if depth == 0 else 0), 6, 7, 7))[port][phase]
                new = ((1, 0, 0, 0), (6, 7, 7, 7))[port][phase]
                hit = int(depth == 0 or phase > 0)
                dirty, ready = int(phase > 0 and not clean), int(phase > 0 and clean)
            else:
                miss = mode in ('companion_miss', 'companion_miss_saturated')
                if port == 1 and mode != 'companion_dirty_hit':
                    selected_depth = 0
                old_a = (0 if mode == 'companion_miss_saturated' else 1) if miss else (
                    5 if depth == 0 else 0)
                old = ((old_a, 0 if miss else 1, 0), (7 if miss else 6, 6 if miss else 7, 7))[port][phase]
                new = ((0 if miss else 1, 0, 0), (6 if miss else 7, 7, 7))[port][phase]
                hit = int(phase > 0 or (miss if port == 0 else not miss))
                dirty = int(phase > 0 or (miss if port == 0 else mode == 'companion_dirty_hit'))
                ready = 0
            result.append(dict(bank=bank, request_port=port, owner=1 - port if cross else port,
                depth=selected_depth, old_counter=old, request_counter=(1, 6)[port],
                new_counter=new, hit=hit, dirty=dirty, ready=ready))
    return tuple(result)


def check_native(checks, shadows, feedback, plan, context):
    expected = deepcopy(plan['initial_shadows'])
    scheduled = {beat.event.tick + 8: frame for beat, frame in
                 zip(feedback, plan['expected_writes'], strict=True)}
    witnesses = []
    for before, following in zip(shadows, shadows[1:]):
        checks.check(expected=2, actual=following.event.tick - before.event.tick, context=context)
        checks.check(expected=expected,
            actual=tuple(row['shadow'] for row in before.value['banks']), context=context)
        ready = tuple(tuple(port['ready'] for port in row['reads']) for row in before.value['banks'])
        checks.check(expected=tuple(tuple(int(any(slot['dirty'] for slot in owner)) for owner in row)
                                   for row in expected),
            actual=tuple(tuple(port['valid'] for port in row['reads']) for row in before.value['banks']),
            context=context)
        frame = scheduled.get(before.event.tick, ((None, None),) * 4)
        transition = advance_tage_shadow_writes(expected, ready, frame)
        if sum(payload is not None for row in frame for payload in row) == 2:
            witnesses.extend(dict(tick=before.event.tick, **item) for item in transition['writes'])
        expected = transition['banks']
        checks.check(expected=expected,
            actual=tuple(row['shadow'] for row in following.value['banks']), context=context)
    wanted = expected_witnesses(plan['bank'], plan['depth'], plan['mode'])
    keys = tuple(wanted[0])
    checks.check(expected=wanted, actual=tuple({key: item[key] for key in keys} for item in witnesses),
                 context=context)
    return witnesses


async def check_case(agent, *, bank, depth, mode):
    plan = await prepare_case(agent, bank, depth, mode)
    transactions = plan['transactions']
    sentinel_pc = 0x40000180 + bank
    sentinel = deepcopy(snapshot(await agent.predict(sentinel_pc, 14, 1)))
    assert not sentinel['meta']['hasProvider']
    comparisons = Scoreboard('tage.dual_shadow_pressure')
    checker = lambda prediction: comparisons.compare(sentinel, snapshot(prediction))
    clean = mode.endswith('_clean')
    async with agent.observe_training() as feedback, agent.observe_writes() as writes, agent.observe_shadows() as shadows:
        predictions = await agent.train_batches_with_read_pressure(
            transactions[:-3] if clean else transactions,
            TageLookup(sentinel_pc, 14, 1), expected=checker)
        if clean:
            for transaction in transactions[-3:]:
                await agent.train_batch(transaction)
    checks = Scoreboard('tage.dual_shadow')
    context = CheckContext(scoreboard='tage.dual_shadow', mode=ScoreboardMode.DIRECT,
        sequence_id=(bank * 4 + depth) * len(DUAL_MODES) + DUAL_MODES.index(mode) + 1,
        request=dict(bank=bank, depth=depth, mode=mode, transactions=transactions),
        accepted_event=feedback[0].event if feedback else None,
        observed_event=writes[-1].event if writes else None)
    checks.check(expected=plan['expected_inputs'],
        actual=tuple(observed_tage_feedback(row.value) for row in feedback), context=context)
    checks.check(expected=plan['expected_writes'], actual=tuple(row.value['banks'] for row in writes), context=context)
    checks.check(expected=(8,) * len(transactions), actual=tuple(write.event.tick - beat.event.tick
        for write, beat in zip(writes, feedback, strict=True)), context=context)
    intervals = [right.event.tick - left.event.tick for left, right in zip(feedback, feedback[1:])]
    boundary = len(transactions) - 4
    checks.check(expected=True, actual=all(value == 2 for value in intervals[:boundary]) and
        all(value > 8 if clean else value == 2 for value in intervals[boundary:]), context=context)
    cadence = tuple((tx.accepted_event.tick, tx.completed_event.tick) for tx in predictions)
    checks.check(expected=True, actual=bool(cadence) and
        all(completed - accepted == 4 for accepted, completed in cadence) and
        all(right[0] - left[0] == 2 for left, right in zip(cadence, cadence[1:])), context=context)
    witnesses = check_native(checks, shadows, feedback, plan, context)
    forward = await read_profiles(agent, plan['expected_profiles'])
    reverse = await read_profiles(agent, plan['expected_profiles'], reverse=True)
    return dict(**{key: value for key, value in plan.items() if key != 'transactions'},
        witnesses=witnesses, native_cycles_checked=len(shadows) - 1, checks=asdict(checks.status),
        forward=forward, reverse=reverse, prediction_cadence=cadence,
        accepted=[dict(tick=row.event.tick, value=row.value) for row in feedback],
        writes=[dict(tick=row.event.tick, value=row.value) for row in writes])
