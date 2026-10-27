"""Two feedback keys overlap a live prediction stream, using domain operations."""
from copy import deepcopy
from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.model.counter import expected_mbtb_counter_activity
from bpuverify.mbtb.model.counter import expected_mbtb_counter_states
from bpuverify.mbtb.case.resident_scenario import INDEX_CONTEXTS
from bpuverify.mbtb.case.resident_scenario import READ_WINDOW
from bpuverify.mbtb.case.resident_scenario import frozen_check
from bpuverify.mbtb.case.resident_scenario import prepare
from bpuverify.mbtb.case.resident_scenario import read_expected
from bpuverify.mbtb.case.resident_scenario import snapshot


async def check_case(agent, coverage, context, align, bank, way, taken, mode):
    vectors, before = await prepare(agent, context, align, bank, way)
    prepared = [snapshot(prediction) for prediction in before]
    # Freeze both counter requests and full resident state before driving.
    states = expected_mbtb_counter_states(prepared, align, way, taken)
    expected_activity = expected_mbtb_counter_activity(
        align, bank, way, taken, mode, sets=INDEX_CONTEXTS[context][:2], reads=READ_WINDOW)
    await read_expected(agent, vectors, prepared)
    sample = dict(context=context, align=align, bank=bank, way=way, taken=taken, mode=mode)
    coverage.sample(dict(sample, phase="prepared"))
    transactions = tuple(MbtbBatchTraining(vector.pc, deepcopy(prediction.meta_entries), (
        MbtbBranchFeedback(vector.target, taken, vector.position, 1, mispredict=1 - taken),
    )) for vector, prediction in zip(vectors[:2], before[:2], strict=True))
    selected = 2 if mode == "blocked" else 3
    async with agent.observe_counter_activity() as trace:
        lookups = [agent.submit_predict(vectors[selected].pc, expected=frozen_check(prepared[selected]))
                   for _ in range(READ_WINDOW)]
        await agent.train_during_predictions_checked(
            transactions, lookups, trace, expected_activity=expected_activity, mode=mode)
        for transfer in lookups:
            await transfer
    await read_expected(agent, vectors, states)
    coverage.sample(dict(sample, phase="updated"))
    await read_expected(agent, vectors, states, reverse=True)
    coverage.sample(dict(sample, phase="revisited"))
