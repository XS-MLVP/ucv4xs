"""Captured feedback with/without overlap, using only domain operations."""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy

from suites.frontend.bpu.tage.transaction.types import TageBaseBranch
from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.model.overlap import expected_tage_overlapped_states
from suites.frontend.bpu.tage.model.overlap import expected_tage_overlapped_writes
from suites.frontend.bpu.tage.case.mixed_writes_scenario import prepare
from suites.frontend.bpu.tage.case.mixed_writes_scenario import prepare_reuse
from suites.frontend.bpu.tage.case.mixed_writes_scenario import read_expected
from suites.frontend.bpu.tage.case.way_migration_scenario import cell
from suites.frontend.bpu.tage.case.way_migration_scenario import snapshot


async def restore(agent, pc, target, victim, way, counter, feedback, protected):
    old = await agent.predict(pc, victim, 0)
    assert old.meta['hasProvider'] == 0, old
    newcomer = await agent.predict(pc, (2 * TAGE_TABLES + 2), 0)
    assert cell(newcomer) == (TAGE_TABLES - 1, 1-way) and newcomer.meta['providerUsefulCtr_value'] == 0, newcomer
    await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
        victim, 1, 0, old.meta, mispredict=1),)), feedback)
    before = await prepare_reuse(agent, pc, target, victim, way, counter, feedback)
    assert not (await agent.predict(pc, (2 * TAGE_TABLES + 2), 0)).meta['hasProvider']
    # Preserve the original independently checked six-neighbor baseline across
    # restoration too; do not silently adopt damaged state as a new baseline.
    await read_expected(agent, pc, protected)
    return before


async def check_case(agent, coverage, pc, context, way, counter, mode, *, pair=None):
    async with agent.observe_training() as feedback:
        if pair is None:
            target, victim, before = await prepare(agent, pc, way, counter, feedback)
            protected = {position:deepcopy(snapshot(pred)) for position,pred in before.items()
                         if position not in (target,victim)}
        else:
            target, victim, protected = pair
            before = await restore(agent, pc, target, victim, way, counter, feedback, protected)
        prepared = {position: deepcopy(snapshot(pred)) for position,pred in before.items()}
        prepared[(2 * TAGE_TABLES + 1)] = prepared[(2 * TAGE_TABLES + 2)] = None
        await read_expected(agent, pc, prepared)
        base = dict(context=context, way=way, counter=counter, mode=mode)
        coverage.sample(dict(base, phase='prepared'))

        # Both snapshots are genuine, captured before either feedback. The
        # resolved branch order stays earlier NT + later taken, not two taken
        # branches in the same block. Only the cold later slot mispredicts.
        transactions = []
        for newcomer in ((2 * TAGE_TABLES + 1), (2 * TAGE_TABLES + 2)):
            prediction = await agent.predict_branches(pc,
                (TageBaseBranch(target, 0), TageBaseBranch(newcomer, 0)))
            assert prediction.metas[0]['providerTakenCtr_value'] == counter
            assert prediction.metas[0]['providerUsefulCtr_value'] == 3
            assert prediction.metas[1]['hasProvider'] == 0
            transactions.append(TageBatchTraining(pc, (
                TageBranchFeedback(target, 0, 0, deepcopy(prediction.metas[0])),)+(None,)*6+(
                TageBranchFeedback(newcomer, 1, 0, deepcopy(prediction.metas[1]), mispredict=1),)))
        expected_writes = expected_tage_overlapped_writes(pc, target, way, counter, mode=mode)
        states = expected_tage_overlapped_states(prepared, target, victim, way)
        async with agent.observe_writes() as writes:
            await agent.train_batches_with_writes_checked(transactions, feedback, writes,
                expected_activity=expected_writes, sequential=mode == 'separated')
        await read_expected(agent, pc, states)
        coverage.sample(dict(base, phase='updated'))
        await read_expected(agent, pc, states, reverse=True)
        coverage.sample(dict(base, phase='revisited'))
        return target, victim, protected
