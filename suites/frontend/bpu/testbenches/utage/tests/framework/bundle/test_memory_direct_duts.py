"""MicroTAGE's production observation layers must bind native memory."""
import pytest

from suites.frontend.bpu.testbenches.utage.env.agent.main import UtageAgent
from suites.frontend.bpu.testbenches.utage.env.monitor.observation import UtageUsefulMonitor
from suites.frontend.bpu.testbenches.utage.env.monitor.shadow import UtageShadowMonitor
from suites.frontend.bpu.testbenches.shared.tests.native_binding import check_observation_bindings


def observation_layers(dut):
    agent = UtageAgent(dut)
    return [UtageUsefulMonitor(agent), *(UtageShadowMonitor(agent, table=table) for table in range(2))]


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param('utage', marks=pytest.mark.dut('utage'))])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    check_observation_bindings(dut, observation_layers)
