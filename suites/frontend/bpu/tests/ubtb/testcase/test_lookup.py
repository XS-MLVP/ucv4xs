"""Cold, gated, allocated and non-allocating MicroBTB lookups."""

from __future__ import annotations

import pytest

from bpuverify.ubtb.checker.assertions import assert_hit
from bpuverify.ubtb.checker.assertions import assert_miss
from bpuverify.ubtb.checker.assertions import train_not_taken
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import CONDITIONAL
from bpuverify.ubtb.case.definitions import DIRECT
from bpuverify.ubtb.case.definitions import INDIRECT
from bpuverify.ubtb.case.definitions import NOT_TAKEN


@pytest.mark.feature("BPU-UBTB-002")
async def test_cold_lookup_misses_and_enable_suppresses_a_hit(ubtb_agent):
    await ubtb_agent.reset()
    await assert_miss(ubtb_agent, DIRECT.pc)
    await train_taken(ubtb_agent, DIRECT)
    await assert_hit(ubtb_agent, DIRECT)

    await ubtb_agent.set_enabled(False)
    await assert_miss(ubtb_agent, DIRECT.pc)
    await ubtb_agent.set_enabled(True)
    await assert_hit(ubtb_agent, DIRECT)


@pytest.mark.feature("BPU-UBTB-003")
@pytest.mark.parametrize("vector", (CONDITIONAL, DIRECT, INDIRECT))
async def test_taken_training_allocates_complete_payload(ubtb_agent, vector):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, vector)
    await assert_hit(ubtb_agent, vector)


@pytest.mark.feature("BPU-UBTB-004")
async def test_not_taken_miss_does_not_allocate(ubtb_agent):
    await ubtb_agent.reset()
    await train_not_taken(ubtb_agent, NOT_TAKEN)
    await assert_miss(ubtb_agent, NOT_TAKEN.pc)
