"""Current MinimalConfig pair contracts, not complete-program FTQ traces."""
from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.model.pair import TagePairModel
from bpuverify.tage.model.pair import TageTableState
from bpuverify.tage.model.constants import TAGE_PAIR_PHASES
from bpuverify.tage.case.definitions import PC


def pair_checker(model, slot, branches, residents=None):
    # Freeze all expected state before requests are submitted. No DUT readback
    # or live mutable reference is consulted when asynchronous comparison runs.
    expected_meta, tables, counter, taken = dict(model.metadata), model.tables, model.alternate.counter, model.taken
    residents = dict(residents or {})

    def compare(prediction):
        assert prediction.metas[slot] == expected_meta, (expected_meta, prediction)
        assert prediction.table_states[slot] == tables, (tables, prediction.table_states)
        assert prediction.alternate_counters[slot] == counter, (counter, prediction.alternate_counters)
        assert (prediction.valids[slot], prediction.takens[slot]) == (1, taken)
        assert prediction.provider_counter_valids == tuple(int(branch is not None) for branch in branches) + (0,)*(4-len(branches))
        for neighbor_slot, branch in enumerate(branches):
            if neighbor_slot == slot or branch is None:
                continue
            table, resident = residents[branch.position]
            expected_tables = tuple(resident if index == table else None for index in range(4))
            assert prediction.table_states[neighbor_slot] == expected_tables, (branch, prediction.table_states)
            meta = prediction.metas[neighbor_slot]
            assert meta == {'hasProvider': 1, 'hasAlt': 0, 'providerTableIdx': table,
                            'providerWayIdx': resident.hit_mask.bit_length()-1,
                            'providerTakenCtr_value': resident.counter, 'providerUsefulCtr_value': resident.useful,
                            'altOrBasePred': branch.taken, 'altConf': branch.base_conf, 'useProvider': 1}
            assert (prediction.valids[neighbor_slot], prediction.takens[neighbor_slot]) == (1, int(resident.counter >= 4))
    return compare


async def prepare_pair(agent, direction, observations):
    residents = {}
    for position in range(16):
        cold = await agent.predict(PC, position, 1-direction, base_conf=1)
        assert cold.meta['hasProvider'] == 0
        await agent.train_checked(TageBatchTraining(PC, (TageBranchFeedback(
            position, direction, 1-direction, cold.meta, mispredict=1),)), observations)
        allocated = await agent.predict(PC, position, 1-direction, base_conf=1)
        table, way = allocated.meta['providerTableIdx'], allocated.meta['providerWayIdx']
        assert allocated.meta['hasProvider'] == 1 and allocated.meta['hasAlt'] == 0
        assert allocated.meta['providerTakenCtr_value'] == (4 if direction else 3)
        # Allocation is LFSR-selected. Do not protect an incidental highest
        # table entry: the table2 -> table3 pair needs a replaceable candidate.
        # Lower-table residents remain protected for the mixed-slot checker.
        if table == 3:
            continue
        for _ in range(4):
            actual_prediction = allocated.taken if allocated.valid else 1-direction
            await agent.train_checked(TageBatchTraining(PC, (TageBranchFeedback(
                position, direction, 1-direction, allocated.meta,
                mispredict=int(actual_prediction != direction)),)), observations)
            allocated = await agent.predict(PC, position, 1-direction, base_conf=1)
        assert allocated.meta['providerTakenCtr_value'] == (7 if direction else 0)
        assert allocated.meta['providerUsefulCtr_value'] == 3
        if table == 2:
            alternate_way = way
            break
        residents[position] = (table, TageTableState(1 << way, 7 if direction else 0, 3))
    else:
        raise AssertionError('normal allocation did not reach table2')
    await agent.train_checked(TageBatchTraining(PC, (TageBranchFeedback(
        position, 1-direction, direction, allocated.meta, mispredict=1),)), observations)
    prediction = await agent.predict(PC, position, direction, base_conf=1)
    assert prediction.meta['providerTableIdx'] == 3 and prediction.meta['hasAlt'] == 1
    assert prediction.meta['providerTakenCtr_value'] == (3 if direction else 4)
    model = TagePairModel(direction, alternate_way=alternate_way, provider_way=prediction.meta['providerWayIdx'])
    return position, model, residents


async def read_slots(agent, position, model, coverage, phase):
    entries = []
    for slot in range(4):
        for base_conf in range(2):
            branches = (None,)*slot + (TageBaseBranch(position, model.direction, base_conf),)
            transfer = agent.submit_predict_branches(PC, branches, expected=pair_checker(model, slot, branches))
            entries.append((transfer, slot, base_conf))
    await agent.drain_predictions()
    ticks = tuple(transfer.accepted_event.tick for transfer, *_ in entries)
    assert ticks == tuple(range(ticks[0], ticks[0]+2*len(entries), 2)), ticks
    assert tuple(transfer.completed_event.tick for transfer, *_ in entries) == tuple(tick+4 for tick in ticks)
    for transfer, slot, base_conf in entries:
        await transfer
        coverage.sample({'direction': model.direction, 'slot': slot, 'base_conf': base_conf, 'phase': phase})


async def drive_pair(agent, position, model, observations, actual, *, slot=7, reason=None):
    # Capture genuine metadata; the state expectation changes independently
    # before the driver sends anything and cannot be seeded by the later output.
    prediction = await agent.predict(PC, position, model.direction, base_conf=1)
    request = TageBranchFeedback(position, actual, model.direction, prediction.meta,
                                mispredict=int(prediction.taken != actual),
                                branch_type=2 if reason == 'direct' else 1,
                                mbtb_hit=0 if reason == 'miss' else 1)
    model.apply(actual, qualified=reason is None)
    if reason == 'disabled':
        await agent.set_enabled(False)
    await agent.train_checked(TageBatchTraining(PC, (None,)*slot + (request,)), observations)
    if reason == 'disabled':
        await agent.set_enabled(True)


async def check_pair_matrix(agent, coverage):
    for direction in range(2):
        await agent.reset()
        async with agent.observe_prediction_state(), agent.observe_training() as observations:
            position, model, _ = await prepare_pair(agent, direction, observations)
            await read_slots(agent, position, model, coverage, 'initial')
            for phase in TAGE_PAIR_PHASES[1:]:
                actual, reason = 1-direction, None
                if phase in ('wrong_provider', 'weak_provider', 'alternate_reentry'):
                    actual = direction
                if phase.endswith('_held') and phase in ('direct_held', 'miss_held', 'disabled_held'):
                    reason = phase.removesuffix('_held')
                if phase == 'weak_provider':
                    await drive_pair(agent, position, model, observations, direction, slot=2)
                await drive_pair(agent, position, model, observations, actual,
                                 slot=TAGE_PAIR_PHASES.index(phase) % 8, reason=reason)
                await read_slots(agent, position, model, coverage, phase)
        assert not (await agent.predict(PC, position, direction)).table_states


async def check_mixed_overlap(agent, coverage):
    for direction in range(2):
        await agent.reset()
        async with agent.observe_prediction_state(), agent.observe_training() as observations:
            position, model, residents = await prepare_pair(agent, direction, observations)
            assert residents, 'mixed layout requires a protected earlier resident'
            await drive_pair(agent, position, model, observations, 1-direction)
            earlier = next(iter(residents))
            for order in ('forward', 'reverse'):
                entries = []
                slots = (1, 2, 3) if order == 'forward' else (3, 2, 1)
                for _ in range(4):
                    for slot in slots:
                        branches = [TageBaseBranch(earlier, 1-direction, base_conf=slot % 2)] + [None]*(slot-1)
                        branches.append(TageBaseBranch(position, direction, base_conf=1))
                        transfer = agent.submit_predict_branches(PC, branches,
                            expected=pair_checker(model, slot, branches, residents))
                        entries.append((transfer, slot))
                await agent.drain_predictions()
                ticks = tuple(transfer.accepted_event.tick for transfer, _ in entries)
                assert ticks == tuple(range(ticks[0], ticks[0]+2*len(entries), 2)), ticks
                assert tuple(transfer.completed_event.tick for transfer, _ in entries) == tuple(tick+4 for tick in ticks)
                for transfer, slot in entries:
                    await transfer
                    coverage.sample({'direction': direction, 'slot': slot, 'order': order})
