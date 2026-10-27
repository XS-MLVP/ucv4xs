"""Keep captured feedback, replacement selection and shadow ownership separate."""
from copy import deepcopy
from dataclasses import replace

from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.transaction.types import MbtbTraining
from bpuverify.mbtb.model.entry import expected_mbtb_entry_states
from bpuverify.mbtb.model.entry import mbtb_retarget_targets
from bpuverify.mbtb.model.shadow import shadow_phase_touch_ways
from bpuverify.mbtb.model.shadow import expected_mbtb_shadow_activity
from bpuverify.mbtb.model.shadow import expected_mbtb_shadow_request_ways
from bpuverify.mbtb.model.shadow import require_mbtb_shadow_cold_metadata
from bpuverify.mbtb.case.resident_scenario import READ_WINDOW
from bpuverify.mbtb.case.resident_scenario import allocate_pair
from bpuverify.mbtb.case.resident_scenario import frozen_check
from bpuverify.mbtb.case.resident_scenario import read_expected
from bpuverify.mbtb.case.resident_scenario import resident_vectors
from bpuverify.mbtb.case.resident_scenario import snapshot


async def prepare(agent, context, align, bank, owner, phase):
    expected_mbtb_shadow_request_ways(owner, phase)
    vectors = resident_vectors(context, align, bank, target_type=3, tag_stride=1)
    await agent.reset()
    cold = await agent.predict(vectors[0].pc)
    assert not any(entry.valid for entry in cold.entries)
    require_mbtb_shadow_cold_metadata(cold.meta_entries)
    captured_cold = deepcopy(cold.meta_entries)
    # Allocate target last so later setup does not displace its retained shadow.
    for index in (1, 2, 3, 0):
        await allocate_pair(agent, vectors[index], owner, neighbor_type=2)
    prepared = [snapshot(await agent.predict(vector.pc)) for vector in vectors]
    for way in shadow_phase_touch_ways(owner, phase):
        touch = prepared[0]['entries'][align * 5 + way]
        await agent.train(MbtbTraining(vectors[0].pc, touch.target, 1, touch.position, touch.branch_type,
                                      deepcopy(prepared[0]["meta_entries"]), mispredict=0))
    # This correct-taken touch must leave full entry/counter/meta state unchanged.
    await read_expected(agent, vectors, prepared)
    return vectors, prepared, captured_cold


async def check_case(agent, coverage, context, align, bank, owner, phase, mode, pattern):
    vectors, prepared, captured_cold = await prepare(agent, context, align, bank, owner, phase)
    vector = vectors[0]
    targets = mbtb_retarget_targets(vector.pc, vector.target, pattern)
    expected = expected_mbtb_shadow_activity(vector.pc, vector.position, owner, targets, mode, phase,
                                           reads=READ_WINDOW)
    states = expected_mbtb_entry_states(prepared, align, owner, targets[-1])
    transactions = tuple(MbtbBatchTraining(vector.pc, deepcopy(captured_cold), (
        MbtbBranchFeedback(target, 1, vector.position, 3, mispredict=1),
    )) for target in targets)
    sample = dict(context=context, align=align, bank=bank, owner=owner, phase=phase, mode=mode, pattern=pattern)
    coverage.sample(dict(sample, status="prepared"))
    sentinel = 2 if mode == "blocked" else 3
    async with agent.observe_entry_activity() as trace:
        lookups = [agent.submit_predict(vectors[sentinel].pc, expected=frozen_check(prepared[sentinel]))
                   for _ in range(READ_WINDOW)]
        await agent.train_entry_during_predictions_checked(transactions, lookups, trace,
                                                          expected_activity=expected, mode=mode)
        for transfer in lookups:
            await transfer
    await read_expected(agent, vectors, states)
    coverage.sample(dict(sample, status="updated"))
    await read_expected(agent, vectors, states, reverse=True)
    coverage.sample(dict(sample, status="revisited"))
