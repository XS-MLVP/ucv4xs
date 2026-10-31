"""Two indirect target rewrites overlap predictions, without low-level IO."""
from copy import deepcopy

from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining
from suites.frontend.bpu.mbtb.transaction.types import MbtbBranchFeedback
from suites.frontend.bpu.mbtb.model.entry import expected_mbtb_entry_activity
from suites.frontend.bpu.mbtb.model.entry import expected_mbtb_entry_states
from suites.frontend.bpu.mbtb.model.entry import mbtb_retarget_targets
from suites.frontend.bpu.mbtb.case.resident_scenario import READ_WINDOW
from suites.frontend.bpu.mbtb.case.resident_scenario import frozen_check
from suites.frontend.bpu.mbtb.case.resident_scenario import prepare
from suites.frontend.bpu.mbtb.case.resident_scenario import read_expected
from suites.frontend.bpu.mbtb.case.resident_scenario import snapshot


async def check_case(agent, coverage, context, align, bank, way, mode, pattern):
    vectors, before = await prepare(agent, context, align, bank, way, target_type=3, neighbor_type=2)
    prepared = [snapshot(prediction) for prediction in before]
    vector = vectors[0]
    targets = mbtb_retarget_targets(vector.pc, vector.target, pattern)
    # Capture two real hit metadata snapshots before either feedback beat.
    captured = [await agent.predict(vector.pc) for _ in targets]
    assert all(snapshot(prediction) == prepared[0] for prediction in captured)
    transactions = tuple(MbtbBatchTraining(vector.pc, deepcopy(prediction.meta_entries), (
        MbtbBranchFeedback(target, 1, vector.position, 3, mispredict=1),
    )) for target, prediction in zip(targets, captured, strict=True))
    # The reference is frozen before driving; no encoder output is its oracle.
    states = expected_mbtb_entry_states(prepared, align, way, targets[-1])
    activity = expected_mbtb_entry_activity(vector.pc, vector.position, way, targets, mode, reads=READ_WINDOW)
    await read_expected(agent, vectors, prepared)
    sample = dict(context=context, align=align, bank=bank, way=way, mode=mode, pattern=pattern)
    coverage.sample(dict(sample, phase="prepared"))
    selected = 2 if mode == "blocked" else 3
    async with agent.observe_entry_activity() as trace:
        lookups = [agent.submit_predict(vectors[selected].pc, expected=frozen_check(prepared[selected]))
                   for _ in range(READ_WINDOW)]
        await agent.train_entry_during_predictions_checked(
            transactions, lookups, trace, expected_activity=activity, mode=mode)
        for transfer in lookups:
            await transfer
    await read_expected(agent, vectors, states)
    coverage.sample(dict(sample, phase="updated"))
    await read_expected(agent, vectors, states, reverse=True)
    coverage.sample(dict(sample, phase="revisited"))
