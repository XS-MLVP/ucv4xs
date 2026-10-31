"""MainBTB conditional taken-counter convergence and saturation."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.checker.assertions import matching_counter
from suites.frontend.bpu.mbtb.checker.assertions import matching_entry
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import CONDITIONAL


@pytest.mark.feature("BPU-MBTB-004")
async def test_conditional_counter_converges_both_directions_without_wrap(mbtb_agent):
    await mbtb_agent.reset()
    prediction = await mbtb_agent.predict(CONDITIONAL.pc)
    await train(mbtb_agent, CONDITIONAL, prediction.meta_entries, taken=1)
    prediction = await mbtb_agent.predict(CONDITIONAL.pc)

    not_taken_trace = []
    not_taken_counters = []
    for _ in range(5):
        await train(mbtb_agent, CONDITIONAL, prediction.meta_entries, taken=0)
        prediction = await mbtb_agent.predict(CONDITIONAL.pc)
        not_taken_trace.append(matching_entry(prediction, CONDITIONAL).taken)
        not_taken_counters.append(matching_counter(prediction, CONDITIONAL))

    taken_trace = []
    taken_counters = []
    for _ in range(5):
        await train(mbtb_agent, CONDITIONAL, prediction.meta_entries, taken=1)
        prediction = await mbtb_agent.predict(CONDITIONAL.pc)
        taken_trace.append(matching_entry(prediction, CONDITIONAL).taken)
        taken_counters.append(matching_counter(prediction, CONDITIONAL))

    assert not_taken_trace[-2:] == [0, 0]
    assert not_taken_counters[-2:] == [0, 0]
    assert taken_trace[-2:] == [1, 1]
    assert taken_counters[-2:] == [3, 3]
