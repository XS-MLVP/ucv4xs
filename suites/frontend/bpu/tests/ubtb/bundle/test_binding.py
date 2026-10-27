"""Picker binding and write-mode contract for MicroBTB."""

from __future__ import annotations


async def test_lookup_and_training_interfaces_use_rise_write(ubtb_agent):
    interfaces = ubtb_agent.ports

    assert ubtb_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.s0_fire.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.fast_train.valid.IsRiseWrite()
    assert interfaces.fast_train.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert interfaces.training.bits.start_pc.IsRiseWrite()
    for branch in interfaces.training.bits.branches:
        assert branch.valid.IsRiseWrite()
        assert branch.target.IsRiseWrite()
        assert branch.ras_action.IsRiseWrite()


async def test_bound_interfaces_expose_protocol_names(ubtb_agent):
    interfaces = ubtb_agent.ports

    assert interfaces.control.name == "ubtb.control"
    assert interfaces.lookup.name == "ubtb.lookup"
    assert interfaces.fast_train.name == "ubtb.fast_train"
    assert interfaces.training.name == "ubtb.training"
    assert interfaces.prediction.name == "ubtb.prediction"
    assert interfaces.status.name == "ubtb.status"
