"""BPU's production observation layers must bind native memory."""
import pytest

from suites.frontend.bpu.testbenches.bpu.env.agent.main import BpuAgent
from suites.frontend.bpu.testbenches.shared.tests.native_binding import check_observation_bindings
from suites.frontend.bpu.testbenches.bpu.env.monitor.phr.observation import BpuPhrMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.sc.observer import ScMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.sc.common_state import CommonStateMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.sc.common_routes import CommonHistoryMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.abtb.observation import IntegratedMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass.policy import SramMonitor


def observation_layers(dut):
    agent = BpuAgent(dut)
    return [BpuPhrMonitor(agent), ScMonitor(agent), CommonStateMonitor(agent),
        CommonHistoryMonitor(agent), IntegratedMonitor(agent), SramMonitor(agent)]


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param('bpu', marks=pytest.mark.dut('bpu'))])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    check_observation_bindings(dut, observation_layers)
