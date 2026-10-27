"""DUTs enter a known reset state before the first simulated clock tick."""

from __future__ import annotations

import pytest

from toffee.signals import sample_signal


@pytest.mark.feature("ENV-IF-002")
@pytest.mark.dut('uras')
def test_dut_factory_asserts_reset_before_clocking(dut_factory):
    dut = dut_factory.create("uras", coverage_name="test_factory_initial_reset-coverage.dat")
    assert sample_signal(dut.reset).as_int() == 1
    assert dut.reset.IsRiseWrite()
    assert dut.clock.IsImmWrite()
    assert sample_signal(dut.io_enable).as_int() == 0
