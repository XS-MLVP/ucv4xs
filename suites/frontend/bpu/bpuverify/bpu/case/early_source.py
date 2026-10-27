"""Check accepted pipeline traffic after a held early-source arbitration."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.bpu.transaction.types import (
    BpuBatchTraining, BpuBranchFeedback, BpuPrediction, BpuRedirect, BpuStage1Source,
)

# XCommClockBackend reports native half-step ticks. This is a time-unit
# conversion for an assertion, not a stimulus or settling interval.
_CLOCK_TICKS_PER_CYCLE = 2


async def check_resumed_arbitration(agent, *, pc, target, position, checkpoint, resolve_meta, micro_target):
    """Release real traffic; do not infer acceptance from a held valid bit.

    Two adjacent accepted requests are the pipeline scenario, not a settling
    delay. Neither source nor target outputs are used to choose the requests.
    Their S3 metadata must echo the complete accepted S1 payload and priority.
    """
    board = Scoreboard('bpu.early_sources.resumed_pipeline')

    def compare(expected, actual, point, request=None):
        board.check(expected=expected, actual=actual, context=CheckContext(
            scoreboard=board.name, mode=ScoreboardMode.DIRECT,
            request=dict(point=point, pc=pc, transaction=request)))

    async def micro_readback(expected_target, point):
        # A pending S2 override may remain on the public output while S1 is
        # held. Validate a genuinely new accepted normal request instead of
        # treating that override as a MicroBTB lookup result.
        await agent.set_ready(prediction=True, meta=True)
        try:
            boundary = await agent.redirect(BpuRedirect(pc, checkpoint))
            actual = await agent.next_transaction(start_pc=pc, after_tick=boundary, limit=128)
            compare(BpuPrediction(pc, expected_target, 1, position, 0, 0), actual.prediction, point, actual)
            compare(BpuStage1Source.UBTB, actual.meta.perf.s1_source, point + '_source', actual)
        finally:
            await agent.set_ready(prediction=False, meta=True)
        await agent.drain_prediction_work()

    # Make the distinct MicroBTB resident an explicit precondition, rather
    # than depend on incidental useful decrements during the held probe.
    # A two-bit useful counter needs at most three decrements and one real
    # replacement. These are feedback transactions, not elapsed cycles.
    await agent.configure_predictors(abtb=False, mbtb=False, settle=True)
    for resident_target in (target, micro_target):
        transaction = BpuBatchTraining(pc, resolve_meta,
            (BpuBranchFeedback(position, resident_target, 3, mispredict=1),))
        accepted_ticks = await agent.train_batches_with_prediction_pause((transaction,) * (1 << 2))
        compare(1 << 2, len(accepted_ticks), 'complete_resolve_retarget_burst')
        compare(tuple(accepted_ticks[0] + index * _CLOCK_TICKS_PER_CYCLE for index in range(1 << 2)),
            accepted_ticks, 'adjacent_same_PC_resolve_retarget_burst')
        await micro_readback(resident_target, 'resolved_MicroBTB_target_before_pipeline')

    await agent.configure_predictors(abtb=True, mbtb=True, settle=True)
    # Re-enabling a predictor cannot retroactively redo the held S0 lookup.
    # Restore the genuine cold context used to train this pair of entries;
    # the checked requests must be new reads after this recovery.
    await agent.redirect(BpuRedirect(pc, checkpoint))
    boundary = await agent.set_ready(prediction=True, meta=True)
    accepted = []
    try:
        for _ in range(128):
            actual = await agent.next_transaction(start_pc=pc, after_tick=boundary, limit=128)
            compare(BpuPrediction(pc, target, 1, position, 0, 0), actual.prediction,
                'accepted_S1_payload', actual)
            compare(BpuStage1Source.ABTB, actual.meta.perf.s1_source,
                'accepted_S1_priority_echoed_at_S3', actual)
            compare((1, position), tuple(actual.meta.resolve['utage']['abtbResult'][0][key]
                for key in ('valid', 'cfiPosition')), 'genuine_ABTB_conditional_metadata', actual)
            accepted.append(actual)
            boundary = actual.prediction_tick
            # Recovery may insert bubbles. Check every accepted payload,
            # including those before the first adjacent pair; never skip
            # mismatches while looking for the pipeline timing condition.
            if len(accepted) >= 2 and accepted[-1].prediction_tick == accepted[-2].prediction_tick + _CLOCK_TICKS_PER_CYCLE:
                break
        compare(True, len(accepted) >= 2
            and accepted[-1].prediction_tick == accepted[-2].prediction_tick + _CLOCK_TICKS_PER_CYCLE,
            'adjacent_accepted_requests', tuple(dict(prediction_tick=row.prediction_tick,
                meta_tick=row.meta_tick, prediction=row.prediction) for row in accepted[-4:]))
    finally:
        await agent.set_ready(prediction=False, meta=True)
    await agent.drain_prediction_work()
    await agent.configure_predictors(abtb=False, mbtb=False, settle=True)
    await micro_readback(target, 'MicroBTB_learns_actual_accepted_final_target')
    return tuple(accepted[-2:])
