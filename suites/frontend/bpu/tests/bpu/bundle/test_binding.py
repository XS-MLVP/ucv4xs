from __future__ import annotations

from toffee import Role, Value, DriveStable, as_xdata


async def test_bpu_ready_valid_and_control_interfaces_are_bound(bpu_agent):
    interfaces = bpu_agent.ports
    assert bpu_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.reset_vector.IsRiseWrite()
    assert interfaces.training.role is Role.PRODUCER
    assert interfaces.prediction.role is Role.MONITOR
    assert interfaces.meta.role is Role.MONITOR
    assert interfaces.redirect.valid.IsRiseWrite()
    fire = interfaces.meta.fire
    assert isinstance(fire,Value) and fire.signal is interfaces.meta.valid and fire.expected == 1
    assert fire.sample == DriveStable(bpu_agent.dut.clock) and fire.mode.value == 'each_sample'
    assert interfaces.meta.ready is as_xdata(interfaces.control.bits.meta_ready)
    assert interfaces.meta.ready.IsInIO() and interfaces.meta.valid.IsOutIO()
