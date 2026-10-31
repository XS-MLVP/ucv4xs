"""AheadBTB lookup transaction encoding."""

from __future__ import annotations

import pytest
from toffee import Bundle

from suites.frontend.bpu.abtb.transaction.types import AbtbLookup
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL


async def test_lookup_encoder_maps_all_pipeline_controls(abtb_agent):
    encode = abtb_agent.lookup_driver.encoder
    assert encode(AbtbLookup(0x4000_0800)) == {
        "s0_fire": 1,
        "s1_fire": 1,
        "s2_fire": 1,
        "start_pc": 0x4000_0800,
        "new_start_pc": 0x4000_0800,
        "path_hash": 0,
        "s2_override": 0,
        "s3_override": 0,
        "override_start_pc": 0x4000_0800,
        "redirect": 0,
    }
    assert encode(AbtbLookup(0x4000_0800, path_hash=0xB))["path_hash"] == 0xB
    s2 = encode(AbtbLookup(0x4000_0800, override="s2", override_pc=0x4000_0820))
    s3 = encode(AbtbLookup(0x4000_0800, override="s3", override_pc=0x4000_0840))
    assert (s2["s2_override"], s2["s3_override"], s2["override_start_pc"]) == (
        1, 0, 0x4000_0820
    )
    assert (s3["s2_override"], s3["s3_override"], s3["override_start_pc"]) == (
        0, 1, 0x4000_0840
    )


async def test_lookup_encoder_aligns_s1_pc_with_previous_s0(abtb_agent):
    first = AbtbLookup(0x4000_0800, path_hash=0)
    second = AbtbLookup(0x4000_1800, path_hash=3)
    abtb_agent.lookup_driver.encoder(first)
    values = abtb_agent.lookup_driver.encoder(second)

    assert values["start_pc"] == second.pc
    assert values["path_hash"] == second.path_hash
    assert values["new_start_pc"] == first.pc


@pytest.mark.feature("BPU-ABTB-009")
async def test_fast_train_valid_and_payload_are_aligned_at_rising_sample(abtb_agent):
    await abtb_agent.reset()
    cold = await abtb_agent.predict(CONDITIONAL.pc)
    training = abtb_agent.ports.training
    monitor = CycleMonitor(
        PortBinding(
            training.clock,
            Bundle(valid=training.valid, bits=training.bits),
            "abtb.training_observation",
        )
    )
    observed = []
    monitor.start(abtb_agent._execution, observer=observed.append)
    try:
        await train_taken(abtb_agent, CONDITIONAL, cold.meta)
    finally:
        await monitor.aclose()

    accepted = [item.value for item in observed if item.value.valid.as_int()]
    assert len(accepted) == 1
    payload = accepted[0].bits
    assert payload.start_pc.as_int() == CONDITIONAL.pc
    assert payload.branch.taken.as_int() == 1
    assert payload.branch.target.as_int() == CONDITIONAL.target
    assert payload.meta.valid.as_int() == 1
    assert payload.meta.setIdx.as_int() == cold.meta["setIdx"]
