"""TAGE's production observation layers must bind native memory."""
import pytest

from suites.frontend.bpu.testbenches.tage.env.agent.main import TageAgent
from suites.frontend.bpu.testbenches.tage.env.monitor.state import TagePredictionStateMonitor
from suites.frontend.bpu.testbenches.tage.env.monitor.write import TageWriteActivityMonitor
from suites.frontend.bpu.testbenches.tage.env.monitor.shadow import TageShadowMonitor
from suites.frontend.bpu.testbenches.shared.tests.native_binding import check_observation_bindings


def observation_layers(dut):
    agent = TageAgent(dut)
    return [TagePredictionStateMonitor(dut, agent.ports.prediction, agent._decode),
        TageWriteActivityMonitor(dut), *(TageShadowMonitor(dut, table=table) for table in range(4))]


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param('tage', marks=pytest.mark.dut('tage'))])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    check_observation_bindings(dut, observation_layers)
