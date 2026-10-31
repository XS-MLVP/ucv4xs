"""Mixed hit/allocation expectations with no signal or edge details."""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy

from suites.frontend.bpu.tage.transaction.types import TageBaseBranch
from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.model.mixed import expected_tage_mixed_writes
from suites.frontend.bpu.tage.case.way_migration_scenario import cell
from suites.frontend.bpu.tage.case.way_migration_scenario import prepare_unprotected_highest_ways
from suites.frontend.bpu.tage.case.way_migration_scenario import read_grid
from suites.frontend.bpu.tage.case.way_migration_scenario import snapshot


async def prepare(agent, pc, way, counter, feedback):
    await prepare_unprotected_highest_ways(agent, pc, origin_way=1-way)
    residents = await read_grid(agent, pc, positions=tuple(range((2 * TAGE_TABLES + 1))))
    target = next(pos for pos, pred in residents.items() if cell(pred) == (TAGE_TABLES - 1, way))
    victim = next(pos for pos, pred in residents.items() if cell(pred) == (TAGE_TABLES - 1, 1-way))
    for expected_counter in range(6, -1, -1):
        pred = await agent.predict(pc, target, 1, base_conf=1)
        await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
            target, 0, 1, pred.meta, mispredict=int((pred.taken if pred.valid else 1) != 0)),)), feedback)
        after = await agent.predict(pc, target, 1, base_conf=1)
        assert cell(after) == (TAGE_TABLES - 1, way) and after.meta['providerTakenCtr_value'] == expected_counter, after
    for _ in range(3):
        pred = await agent.predict(pc, target, 1, base_conf=1)
        await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(target, 0, 1, pred.meta),)), feedback)
    for _ in range(counter):
        pred = await agent.predict(pc, target, 0)
        await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(target, 1, 0, pred.meta, mispredict=1),)), feedback)
    before = await read_grid(agent, pc, positions=tuple(range((2 * TAGE_TABLES + 1))))
    assert before[target].meta['providerTakenCtr_value'] == counter
    assert before[target].meta['providerUsefulCtr_value'] == 3
    assert before[victim].meta['providerUsefulCtr_value'] == 0
    assert target < (2 * TAGE_TABLES + 1) and (2 * TAGE_TABLES + 1) not in before
    for pos, pred in before.items():
        if pos not in (target, victim):
            assert pred.meta['providerTakenCtr_value'] == 7 and pred.meta['providerUsefulCtr_value'] == 3, pred
    return target, victim, before


def checker(expected, *, absent=False):
    expected = deepcopy(expected)

    def compare(pred):
        # TAGE's taken-valid/meta can expose a hit for an unused MainBTB slot;
        # only the to-SC provider-counter-valid is gated by branch.valid.
        assert pred.provider_counter_valids[1:] == (0,) * (RESULT_SLOTS - 1), pred
        if absent:
            assert (pred.valid, pred.provider_counter_valid, pred.meta['hasProvider']) == (0, 0, 0), pred
        else:
            assert snapshot(pred) == expected, (expected, pred)
    return compare


async def prepare_reuse(agent, pc, target, victim, way, counter, feedback):
    """Restore using normal transactions, not another 256-failure aging sweep.

    Each context/way starts with a fresh sweep. Subsequent cases reuse that
    protected family: replace the unprotected newcomer with the old victim,
    and set the target to the desired non-weak NT counter. Every later state
    expectation remains frozen from the requested counter, not actual after.
    """
    old = await agent.predict(pc, victim, 0)
    if not old.meta['hasProvider']:
        newcomer = await agent.predict(pc, (2 * TAGE_TABLES + 1), 0)
        assert cell(newcomer) == (TAGE_TABLES - 1, 1-way) and newcomer.meta['providerUsefulCtr_value'] == 0
        await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
            victim, 1, 0, old.meta, mispredict=1),)), feedback)
    for _ in range(3):
        pred = await agent.predict(pc, target, 0)
        assert cell(pred) == (TAGE_TABLES - 1, way) and pred.meta['providerUsefulCtr_value'] == 3, pred
        current = pred.meta['providerTakenCtr_value']
        assert 0 <= current <= 2, pred
        if current == counter:
            break
        taken = int(current < counter)
        await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
            target, taken, 0, pred.meta, mispredict=taken),)), feedback)
    before = await read_grid(agent, pc, positions=tuple(range((2 * TAGE_TABLES + 1))))
    assert before[target].meta['providerTakenCtr_value'] == counter
    assert cell(before[victim]) == (TAGE_TABLES - 1, 1-way) and before[victim].meta['providerUsefulCtr_value'] == 0
    assert not (await agent.predict(pc, (2 * TAGE_TABLES + 1), 0)).meta['hasProvider']
    return before


async def read_expected(agent, pc, states, *, reverse=False):
    positions = tuple(states)
    if reverse:
        positions = tuple(reversed(positions)) + positions
    transfers = [agent.submit_predict(pc, pos, 0, expected=checker(states[pos], absent=states[pos] is None))
                 for pos in positions]
    await agent.drain_predictions()
    accepted = tuple(transfer.accepted_event.tick for transfer in transfers)
    assert accepted == tuple(range(accepted[0], accepted[0]+2*len(transfers), 2)), accepted
    assert tuple(transfer.completed_event.tick for transfer in transfers) == tuple(tick+4 for tick in accepted)
    for transfer in transfers:
        await transfer


async def check_case(agent, coverage, pc, context, way, counter, *, reason=None, pair=None):
    async with agent.observe_training() as feedback:
        if pair is None:
            target, victim, before = await prepare(agent, pc, way, counter, feedback)
        else:
            target, victim = pair
            before = await prepare_reuse(agent, pc, target, victim, way, counter, feedback)
        prepared = {pos: deepcopy(snapshot(pred)) for pos, pred in before.items()}
        prepared[(2 * TAGE_TABLES + 1)] = None
        await read_expected(agent, pc, prepared)
        axis = {'counter': counter} if reason is None else {'reason': reason}
        base = dict(context=context, way=way, **axis)
        coverage.sample(dict(base, phase='prepared'))
        pred = await agent.predict_branches(pc, (TageBaseBranch(target, 0), TageBaseBranch((2 * TAGE_TABLES + 1), 0)))
        assert pred.metas[0]['providerTakenCtr_value'] == counter and pred.metas[1]['hasProvider'] == 0
        early = TageBranchFeedback(target, 0, 0, pred.metas[0], valid=int(reason != 'inactive'),
                                   mbtb_hit=int(reason != 'mbtb_miss'))
        transaction = TageBatchTraining(pc, (early,)+(None,)*6+(TageBranchFeedback((2 * TAGE_TABLES + 1), 1, 0, pred.metas[1], mispredict=1),))
        qualified, allocation = reason not in ('mbtb_miss', 'inactive', 'disabled'), reason != 'disabled'
        expected_activity = expected_tage_mixed_writes(pc, target, way, counter, qualified=qualified, allocation=allocation)
        states = deepcopy(prepared)
        if qualified and counter:
            states[target]['meta']['providerTakenCtr_value'] = counter-1
        if allocation:
            states[victim] = None
            states[(2 * TAGE_TABLES + 1)] = {'valid': 1, 'taken': 1, 'provider_counter_valid': 1, 'meta': {
                'hasProvider': 1, 'hasAlt': 0, 'providerTableIdx': TAGE_TABLES - 1, 'providerWayIdx': 1-way,
                'providerTakenCtr_value': 4, 'providerUsefulCtr_value': 0,
                'useProvider': 1, 'altConf': 0, 'altOrBasePred': 0,
            }}
        if reason == 'disabled':
            await agent.set_enabled(False)
        try:
            async with agent.observe_writes() as writes:
                await agent.train_with_writes_checked(transaction, feedback, writes, expected_activity=expected_activity)
        finally:
            if reason == 'disabled':
                await agent.set_enabled(True)
        await read_expected(agent, pc, states)
        coverage.sample(dict(base, phase='updated'))
        await read_expected(agent, pc, states, reverse=True)
        coverage.sample(dict(base, phase='revisited'))
        return target, victim
