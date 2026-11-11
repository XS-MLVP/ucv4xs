"""ABTB's production observation layers must bind native memory."""
import pytest

from suites.frontend.bpu.testbenches.abtb.env.agent.main import AbtbAgent
from suites.frontend.bpu.testbenches.abtb.env.monitor.state.writebuffer import CapacityMonitor
from suites.frontend.bpu.testbenches.abtb.env.monitor.state.replacer import ReplacerMonitor
from suites.frontend.bpu.testbenches.shared.tests.native_binding import check_observation_bindings


def observation_layers(dut):
    agent = AbtbAgent(dut)
    return [CapacityMonitor(agent), ReplacerMonitor(agent)]


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param('abtb', marks=pytest.mark.dut('abtb'))])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    check_observation_bindings(dut, observation_layers)
