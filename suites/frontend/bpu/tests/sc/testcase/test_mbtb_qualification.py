"""SC corrects only valid conditional MBTB predictions."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.sc.checker.assertions import learn
from suites.frontend.bpu.sc.case.definitions import PC
from suites.frontend.bpu.sc.case.definitions import POSITION
from suites.frontend.bpu.sc.case.definitions import TAGE_COUNTER


@pytest.mark.feature("BPU-SC-007")
async def test_mbtb_miss_suppresses_trained_sc_override(sc_agent):
    await sc_agent.reset()
    learned = await learn(sc_agent, 1)
    assert (learned.used, learned.taken) == (1, 1)

    miss = await sc_agent.predict(PC, POSITION, TAGE_COUNTER, mbtb_valid=0)
    assert miss.used == 0, miss
    restored = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
    assert (restored.used, restored.taken) == (1, 1), restored


@pytest.mark.feature("BPU-SC-008")
async def test_nonconditional_mbtb_hit_suppresses_trained_sc_override(sc_agent):
    await sc_agent.reset()
    learned = await learn(sc_agent, 1)
    assert (learned.used, learned.taken) == (1, 1)

    direct = await sc_agent.predict(PC, POSITION, TAGE_COUNTER, branch_type=2)
    assert direct.used == 0, direct
    restored = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
    assert (restored.used, restored.taken) == (1, 1), restored
