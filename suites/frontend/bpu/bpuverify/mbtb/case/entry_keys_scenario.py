"""bpuverify.mbtb.case.entry_keys_scenario components."""
from copy import deepcopy

from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.model.entry_keys import expected_mbtb_entry_keys_activity
from bpuverify.mbtb.model.entry_keys import expected_mbtb_entry_keys_states
from bpuverify.mbtb.model.entry_keys import mbtb_entry_key_targets
from bpuverify.mbtb.case.resident_scenario import READ_WINDOW
from bpuverify.mbtb.case.resident_scenario import frozen_check
from bpuverify.mbtb.case.resident_scenario import prepare
from bpuverify.mbtb.case.resident_scenario import read_expected
from bpuverify.mbtb.case.resident_scenario import snapshot
from bpuverify.mbtb.model.entry import summarize_mbtb_entry_activity


async def check_case(agent, coverage, context, align, bank, way, mode, order, pair):
    if order not in ("first_second", "second_first"):
        raise ValueError("entry key order must identify both keys")
    vectors, before = await prepare(agent, context, align, bank, way,
                                   target_type=3, neighbor_type=2, tag_stride=1)
    original_metadata=deepcopy(tuple(p.meta_entries for p in before))
    prepared = [snapshot(prediction) for prediction in before]
    pcs = tuple(vector.pc for vector in vectors[:2])
    targets = mbtb_entry_key_targets(pcs, tuple(vector.target for vector in vectors[:2]), pair)
    # Submission order must not change which target belongs to which PC.
    indices = (0, 1) if order == "first_second" else (1, 0)
    states = expected_mbtb_entry_keys_states(prepared, align, way, targets)
    expected_activity = expected_mbtb_entry_keys_activity(
        tuple(pcs[index] for index in indices), vectors[0].position, way,
        tuple(targets[index] for index in indices), mode, reads=READ_WINDOW)
    transactions = tuple(MbtbBatchTraining(vectors[index].pc, deepcopy(before[index].meta_entries), (
        MbtbBranchFeedback(targets[index], 1, vectors[index].position, 3, mispredict=1),
    )) for index in indices)
    await read_expected(agent, vectors, prepared)
    sample = dict(context=context, align=align, bank=bank, way=way, mode=mode, order=order, pair=pair)
    coverage.sample(dict(sample, phase="prepared"))
    sentinel = 2 if mode == "blocked" else 3
    async with agent.observe_entry_activity() as trace:
        lookups = [agent.submit_predict(vectors[sentinel].pc, expected=frozen_check(prepared[sentinel]))
                   for _ in range(READ_WINDOW)]
        await agent.train_entry_during_predictions_checked(
            transactions, lookups, trace, expected_activity=expected_activity, mode=mode)
        for transfer in lookups:
            await transfer
    await read_expected(agent, vectors, states)
    coverage.sample(dict(sample, phase="updated"))
    await read_expected(agent, vectors, states, reverse=True)
    agent.reference.raise_failure()
    assert original_metadata==tuple(p.meta_entries for p in before),'original feedback metadata changed'
    coverage.sample(dict(sample, phase="revisited"))
    status=agent.reference.board.status
    return dict(expected_activity=expected_activity,
        actual_activity=summarize_mbtb_entry_activity(trace.frames,trace.feedback,lookups,mode),
        original_metadata_unchanged=True,independent_reference_checks=status.checked,
        independent_reference_failures=status.failed)
