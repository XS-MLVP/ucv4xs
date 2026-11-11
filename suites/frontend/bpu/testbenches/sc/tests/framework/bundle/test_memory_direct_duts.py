"""SC's production observation layers must bind native memory."""
import pytest

from suites.frontend.bpu.testbenches.sc.env.monitor.threshold import ScThresholdMonitor
from suites.frontend.bpu.testbenches.shared.tests.native_binding import check_observation_bindings


def observation_layers(dut):
    return [ScThresholdMonitor(dut)]


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param('sc', marks=pytest.mark.dut('sc'))])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    check_observation_bindings(dut, observation_layers)
