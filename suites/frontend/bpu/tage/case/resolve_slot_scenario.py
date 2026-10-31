"""Sparse resolve-port contracts; no claim of full-program FTQ trace legality."""
from suites.frontend.bpu.models.configuration import *
from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.checker.assertions import prepare_highest_provider, await_cold_allocation
from suites.frontend.bpu.tage.case.definitions import PC


def state(prediction):
    return tuple(prediction.meta[key] for key in (
        'hasProvider', 'providerTableIdx', 'providerWayIdx',
        'providerTakenCtr_value', 'providerUsefulCtr_value',
    ))


def require_state(expected, *, taken=None):
    def compare(prediction):
        assert state(prediction) == expected, (expected, prediction)
        if taken is not None:
            assert (prediction.valid, prediction.taken, prediction.meta['useProvider']) == (1, taken, 1), prediction
    return compare


async def read_residents(agent, positions, base, expected=None, *, taken=None):
    transfers = [agent.submit_predict(
        PC, position, base, base_conf=1,
        **({} if expected is None else {'expected': require_state(expected[position], taken=taken)}),
    ) for position in positions]
    await agent.drain_predictions()
    ticks = tuple(transfer.accepted_event.tick for transfer in transfers)
    assert ticks == tuple(range(ticks[0], ticks[0] + 2 * len(ticks), 2)), ticks
    assert tuple(transfer.completed_event.tick for transfer in transfers) == tuple(tick + 4 for tick in ticks)
    return {position: await transfer for position, transfer in zip(positions, transfers, strict=True)}


def sparse(slot, target, *, neighbor=None):
    branches = [None] * 8
    branches[slot] = target
    if neighbor is not None:
        # Preserve CFI order in the multi-active cases. Slot zero has a later
        # neighbor; the other targets have an earlier neighbor in slot zero.
        branches[1 if slot == 0 else 0] = neighbor
    return TageBatchTraining(PC, tuple(branches))


def feedback(position, prediction, actual, base, *, mispredict=None, **changes):
    if mispredict is None:
        mispredict = int((prediction.taken if prediction.valid else base) != actual)
    return TageBranchFeedback(position, actual, base, prediction.meta, mispredict=mispredict,
                              base_counter_value=3 if base else 0, **changes)


async def check_provider_matrix(agent, coverage):
    for slot in range(8):
        for direction in range(2):
            await agent.reset()
            base = 1 - direction
            expected = {}
            seen = set()
            async with agent.observe_training() as observations:
                for position in range(TAGE_TABLES):
                    cold = await agent.predict(PC, position, base, base_conf=1)
                    assert cold.meta['hasProvider'] == 0, cold
                    desired = await await_cold_allocation(agent, pc=PC, position=position, taken=direction, base=base, table=position)
                    await agent.train_checked(sparse(slot, feedback(position, cold, direction, base)), observations)
                    allocated = await agent.predict(PC, position, base, base_conf=1)
                    assert allocated.meta['hasProvider'] == 1 and allocated.meta['hasAlt'] == 0, allocated
                    depth, way = allocated.meta['providerTableIdx'], allocated.meta['providerWayIdx']
                    assert (depth, way) == desired
                    counter = 4 if direction else 3
                    expected[position] = (1, depth, way, counter, 0)
                    current = await read_residents(agent, tuple(expected), base, expected)
                    coverage.sample({'slot': slot, 'direction': direction, 'depth': depth, 'phase': 'allocated'})
                    useful = 0
                    for phase in ('strengthened', 'near_saturated', 'saturated', 'held'):
                        prediction = current[position]
                        assert prediction.meta['altOrBasePred'] == base
                        counter = min(7, counter + 1) if direction else max(0, counter - 1)
                        useful = min(3, useful + 1)
                        expected[position] = (1, depth, way, counter, useful)
                        await agent.train_checked(sparse(slot, feedback(position, prediction, direction, base)), observations)
                        current = await read_residents(agent, tuple(expected), base, expected, taken=direction)
                        coverage.sample({'slot': slot, 'direction': direction, 'depth': depth, 'phase': phase})
                    seen.add(depth)
                    if seen == set(range(TAGE_TABLES)):
                        break
                assert seen == set(range(TAGE_TABLES)), (slot, direction, seen)


async def check_qualification_matrix(agent, coverage):
    for slot in range(8):
        await agent.reset()
        target_position = 6
        target = await prepare_highest_provider(agent, pc=PC, position=target_position, taken=1)
        target_before = state(target)
        neighbor_position = 7 if slot == 0 else 2
        # A separate tag remains absent throughout ignored neighbor feedback.
        neighbor_cond = await agent.predict(PC, neighbor_position, 0, base_conf=1)
        assert neighbor_cond.meta['hasProvider'] == 0
        neighbor_direct = await agent.predict(PC, neighbor_position, 0, base_conf=1, branch_type=2)
        ignored_neighbor = feedback(neighbor_position, neighbor_cond, 0, 0, mispredict=0, mbtb_hit=0)
        async with agent.observe_training() as observations:
            for reason, changes in (
                ('mbtb_miss', {'mbtb_hit': 0}), ('direct', {'branch_type': 2}),
                ('indirect', {'branch_type': 3}), ('inactive', {'valid': 0}), ('disabled', {}),
            ):
                before = await agent.predict(PC, target_position, 0, base_conf=1)
                assert state(before) == target_before
                transaction = sparse(slot, feedback(target_position, before, 0, 0, **changes),
                                     neighbor=ignored_neighbor)
                if reason == 'disabled':
                    await agent.set_enabled(False)
                await agent.train_checked(transaction, observations)
                if reason == 'disabled':
                    await agent.set_enabled(True)
                after = await agent.predict(PC, target_position, 0, base_conf=1)
                assert state(after) == target_before, (slot, reason, before, after)
                assert (await agent.predict(PC, neighbor_position, 0)).meta['hasProvider'] == 0
                coverage.sample({'slot': slot, 'reason': reason})

            for reason, neighbor in (
                ('qualified_missed_neighbor', ignored_neighbor),
                ('qualified_nonconditional_neighbor', feedback(
                    neighbor_position, neighbor_direct, 0, 0, mispredict=0, branch_type=2,
                )),
            ):
                before = await agent.predict(PC, target_position, 0, base_conf=1)
                actual = 0 if reason == 'qualified_missed_neighbor' else 1
                expected = list(state(before))
                expected[3] += 1 if actual else -1
                provider_pred = int(before.meta['providerTakenCtr_value'] >= 4)
                if provider_pred == actual and provider_pred != before.meta['altOrBasePred']:
                    expected[4] = min(3, expected[4] + 1)
                await agent.train_checked(sparse(
                    slot, feedback(target_position, before, actual, 0), neighbor=neighbor,
                ), observations)
                transfer = agent.submit_predict(PC, target_position, 0, base_conf=1,
                                                expected=require_state(tuple(expected)))
                await agent.drain_predictions()
                await transfer
                assert (await agent.predict(PC, neighbor_position, 0)).meta['hasProvider'] == 0
                coverage.sample({'slot': slot, 'reason': reason})
