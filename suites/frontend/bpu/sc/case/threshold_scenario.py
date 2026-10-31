"""Threshold scenarios consume real metadata and compare full monitored state.

These are standalone SC feedback-port contracts, not full-program FTQ traces.
The eight-way DefaultConfig and picker GuardedPc.addr units are explicit.
"""
from suites.frontend.bpu.models.configuration import SC_WAYS, SC_TABLES, RESULT_SLOTS, MAIN_WAYS, SC_MIN_THRESHOLD, SC_MAX_THRESHOLD

from suites.frontend.bpu.sc.transaction.types import ScBaseBranch
from suites.frontend.bpu.sc.transaction.types import ScBatchTraining
from suites.frontend.bpu.sc.transaction.types import ScBranchFeedback
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel

INITIAL, MINIMUM, MAXIMUM = 1130, SC_MIN_THRESHOLD, SC_MAX_THRESHOLD
POSITIONS_BY_WAY = tuple(tuple(p for p in range(32) if (p % SC_WAYS) ^ (p // SC_WAYS) == way) for way in range(SC_WAYS))


def make_feedback(pc, prediction, positions, wrong, *, slots=None, **branch_changes):
    slots = tuple(range(len(positions))) if slots is None else slots
    return ScBatchTraining(pc, prediction.meta, tuple(
        ScBranchFeedback(position, int(prediction.meta['scPred'][slot]) ^ int(mispredicted),
                         slot, **branch_changes)
        for position, slot, mispredicted in zip(positions, slots, wrong, strict=True)
    ))


async def check_feedback(agent, model, feedback, *, enabled=True):
    update = model.apply(feedback, enabled=enabled)
    await agent.train_batch(feedback)
    await agent.check_thresholds(update.after, request=feedback)
    return update


def lower_pc(step):
    # Both hardware banks and all 128 bank/bias rows prevent confidence gating
    # from stopping correct feedback before the custom lower bound.
    return 0x40000040 + 0x10 * (((step - 1) // 2) % 128) + (step - 1) % 2


async def check_single_boundaries(agent, coverage):
    positions = tuple(range(SC_WAYS))
    layout = tuple(ScBaseBranch(position, 7) for position in positions)
    for boundary, target, limit in (('lower', MINIMUM, 800), ('upper', MAXIMUM, MAXIMUM - INITIAL + 16)):
        await agent.reset()
        model = ScThresholdModel.for_default()
        await agent.check_thresholds(model.values)
        rejected = [0] * SC_WAYS
        rows = set()
        reached = False
        for step in range(1, limit + 1):
            pc = lower_pc(step) if boundary == 'lower' else 0x40000040
            prediction = await agent.predict_branches(pc, layout)
            rows.add((pc & 1, prediction.meta['debug']['predBiasIdx']))
            feedback = make_feedback(pc, prediction, positions, (boundary == 'upper',) * SC_WAYS)
            update = await check_feedback(agent, model, feedback)
            for way in update.rejected_ways:
                rejected[way] += 1
                assert update.before[way] == update.after[way] == target
            if model.values == (target,) * SC_WAYS and not reached:
                reached = True
                for way in range(SC_WAYS):
                    coverage.sample({'boundary': boundary, 'way': way, 'phase': 'approach'})
            if reached and min(rejected) >= 4:
                break
        assert reached and min(rejected) >= 4, (boundary, model.values, rejected)
        if boundary == 'lower':
            assert len(rows) == min(step, 256), rows
        for way in range(SC_WAYS):
            coverage.sample({'boundary': boundary, 'way': way, 'phase': 'reject'})
        prediction = await agent.predict_branches(pc, layout)
        feedback = make_feedback(pc, prediction, positions, (boundary == 'lower',) * SC_WAYS)
        update = await check_feedback(agent, model, feedback)
        assert len(update.qualifying_slots) == SC_WAYS
        inward = 1 if boundary == 'lower' else -1
        assert update.after == (target + inward,) * SC_WAYS
        for way in range(SC_WAYS):
            coverage.sample({'boundary': boundary, 'way': way, 'phase': 'recover'})


async def check_multi_boundaries(agent, coverage):
    for way, positions in enumerate(POSITIONS_BY_WAY):
        layout = tuple(ScBaseBranch(position, 7) for position in positions)
        for boundary, target, limit in (('lower', MINIMUM + (INITIAL - MINIMUM) % 4, (INITIAL - MINIMUM) // 4 + 16), ('upper', MAXIMUM - (MAXIMUM - INITIAL) % 4, (MAXIMUM - INITIAL) // 4 + 16)):
            await agent.reset()
            model = ScThresholdModel.for_default()
            await agent.check_thresholds(model.values)
            rejects = 0
            reached = False
            for step in range(1, limit + 1):
                pc = lower_pc(step) if boundary == 'lower' else 0x40000040
                prediction = await agent.predict_branches(pc, layout)
                feedback = make_feedback(pc, prediction, positions, (boundary == 'upper',) * 4)
                update = await check_feedback(agent, model, feedback)
                assert update.qualifying_slots == (0, 1, 2, 3)
                assert all(value == INITIAL for other, value in enumerate(update.after) if other != way)
                if update.after[way] == target and not reached:
                    reached = True
                    coverage.sample({'boundary': boundary, 'way': way, 'phase': 'approach'})
                if way in update.rejected_ways:
                    assert update.before[way] == update.after[way] == target
                    rejects += 1
                if rejects >= 4:
                    break
            assert reached and rejects >= 4, (way, boundary, model.values, rejects)
            coverage.sample({'boundary': boundary, 'way': way, 'phase': 'reject'})
            prediction = await agent.predict_branches(pc, layout)
            update = await check_feedback(agent, model, make_feedback(
                pc, prediction, positions, (boundary == 'lower',) * 4,
            ))
            inward = 4 if boundary == 'lower' else -4
            assert update.after[way] == target + inward
            assert len(update.qualifying_slots) == 4
            coverage.sample({'boundary': boundary, 'way': way, 'phase': 'recover'})


async def check_qualification_and_aggregation(agent, coverage):
    for way, positions in enumerate(POSITIONS_BY_WAY):
        await agent.reset()
        model = ScThresholdModel.for_default()
        await agent.check_thresholds(model.values)
        pc = 0x40000040
        layout = tuple(ScBaseBranch(positions[0], 7) if slot == way else None for slot in range(RESULT_SLOTS))
        prediction = await agent.predict_branches(pc, layout)
        feedback = make_feedback(pc, prediction, positions[:1], (True,), slots=(way,))
        update = await check_feedback(agent, model, feedback)
        assert update.qualifying_slots == (way,) and update.increments[way] == 1
        coverage.sample({'way': way, 'reason': 'qualified_wrong'})

        for reason, changes in (('mbtb_miss', {'mbtb_hit': 0}), ('nonconditional', {'branch_type': 2})):
            prediction = await agent.predict_branches(pc, layout)
            update = await check_feedback(agent, model, make_feedback(
                pc, prediction, positions[:1], (True,), slots=(way,), **changes,
            ))
            assert update.after == update.before and not update.qualifying_slots
            coverage.sample({'way': way, 'reason': reason})

        invalid_layout = tuple(ScBaseBranch(positions[0], 7, provider_valid=0) if slot == way else None
                               for slot in range(RESULT_SLOTS))
        prediction = await agent.predict_branches(pc, invalid_layout)
        assert prediction.meta['tagePredValid'][way] == 0
        update = await check_feedback(agent, model, make_feedback(
            pc, prediction, positions[:1], (True,), slots=(way,),
        ))
        assert update.after == update.before and not update.qualifying_slots
        coverage.sample({'way': way, 'reason': 'provider_invalid'})

        prediction = await agent.predict_branches(pc, layout)
        feedback = make_feedback(pc, prediction, positions[:1], (True,), slots=(way,))
        await agent.set_enabled(False)
        update = await check_feedback(agent, model, feedback, enabled=False)
        assert update.after == update.before and not update.qualifying_slots
        await agent.set_enabled(True)
        coverage.sample({'way': way, 'reason': 'disabled'})

        for row, (reason, wrong, inc, dec) in enumerate((
            ('net_zero', (True, False), 1, 1),
            ('net_positive', (True, True, False), 2, 1),
            ('net_negative', (False, False, True), 1, 2),
        ), start=1):
            mixed_pc = pc + row * 0x10
            mixed_layout = tuple(ScBaseBranch(position, 7) for position in positions[:len(wrong)])
            prediction = await agent.predict_branches(mixed_pc, mixed_layout)
            assert prediction.meta['sumAboveThres'][:len(wrong)] == (0,) * len(wrong)
            update = await check_feedback(agent, model, make_feedback(
                mixed_pc, prediction, positions[:len(wrong)], wrong,
            ))
            assert len(update.qualifying_slots) == len(wrong)
            assert (update.increments[way], update.decrements[way]) == (inc, dec)
            assert update.after[way] == update.before[way] + inc - dec
            coverage.sample({'way': way, 'reason': reason})

        burst = []
        for _ in range(4):
            prediction = await agent.predict_branches(pc, layout)
            burst.append(make_feedback(pc, prediction, positions[:1], (True,), slots=(way,)))
        before_count = len(agent.training_observations)
        updates = model.apply_many(burst)
        assert updates[-1].after[way] == updates[0].before[way] + 4
        await agent.train_batches(burst)
        await agent.check_thresholds(model.values, request=tuple(burst))
        observations = agent.training_observations[before_count:]
        assert len(observations) == 4
        ticks = tuple(observation.event.tick for observation in observations)
        assert tuple(right - left for left, right in zip(ticks, ticks[1:])) == (2, 2, 2), ticks
        coverage.sample({'way': way, 'reason': 'adjacent_burst'})

        for _ in range(80):
            prediction = await agent.predict_branches(pc, layout)
            if (prediction.meta['sumAboveThres'][way] and prediction.meta['useScPred'][way]
                    and prediction.meta['scPred'][way] == prediction.meta['tagePred'][way]):
                break
            update = await check_feedback(agent, model, make_feedback(
                pc, prediction, positions[:1], (False,), slots=(way,),
            ))
        else:
            raise AssertionError(f'SC way {way} did not reach genuinely confident agreeing metadata')
        update = await check_feedback(agent, model, make_feedback(
            pc, prediction, positions[:1], (False,), slots=(way,),
        ))
        assert update.after == update.before and not update.qualifying_slots
        coverage.sample({'way': way, 'reason': 'confident_correct'})
