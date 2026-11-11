"""MicroRAS's native binding must use the shared memory-direct interface."""
import pytest

from suites.frontend.bpu.testbenches.shared.tests.native_binding import check_observation_bindings


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param('uras', marks=pytest.mark.dut('uras'))])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    check_observation_bindings(dut, lambda dut: [])
