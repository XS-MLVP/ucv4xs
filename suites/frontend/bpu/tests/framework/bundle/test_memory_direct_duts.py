"""Every installed DUT and production observation layer must bind native memory."""
import pytest

from suites.frontend.bpu.abtb.agent.main import AbtbAgent
from suites.frontend.bpu.bpu.agent.main import BpuAgent
from suites.frontend.bpu.ras.agent.main import RasAgent
from suites.frontend.bpu.tage.agent.main import TageAgent
from suites.frontend.bpu.utage.agent.main import UtageAgent
from suites.frontend.bpu.runtime.memory_direct import require_memory_direct
from suites.frontend.bpu.abtb.monitor.state.writebuffer import CapacityMonitor
from suites.frontend.bpu.abtb.monitor.state.replacer import ReplacerMonitor
from suites.frontend.bpu.bpu.monitor.phr.observation import BpuPhrMonitor
from suites.frontend.bpu.bpu.monitor.sc.observer import ScMonitor
from suites.frontend.bpu.bpu.monitor.sc.common_state import CommonStateMonitor
from suites.frontend.bpu.bpu.monitor.sc.common_routes import CommonHistoryMonitor
from suites.frontend.bpu.bpu.monitor.abtb.observation import IntegratedMonitor
from suites.frontend.bpu.bpu.monitor.bypass.policy import SramMonitor
from suites.frontend.bpu.mbtb.monitor.counter import MbtbCounterActivityMonitor
from suites.frontend.bpu.mbtb.monitor.entry import MbtbEntryActivityMonitor
from suites.frontend.bpu.mbtb.monitor.shadow import MbtbEntryShadowMonitor
from suites.frontend.bpu.ras.monitor.observation import RasCommittedMonitor
from suites.frontend.bpu.sc.monitor.threshold import ScThresholdMonitor
from suites.frontend.bpu.tage.monitor.state import TagePredictionStateMonitor
from suites.frontend.bpu.tage.monitor.write import TageWriteActivityMonitor
from suites.frontend.bpu.tage.monitor.shadow import TageShadowMonitor
from suites.frontend.bpu.utage.monitor.observation import UtageUsefulMonitor
from suites.frontend.bpu.utage.monitor.shadow import UtageShadowMonitor


def observation_layers(name, dut):
    if name == 'abtb':
        agent = AbtbAgent(dut)
        return [CapacityMonitor(agent), ReplacerMonitor(agent)]
    if name == 'bpu':
        agent = BpuAgent(dut)
        return [BpuPhrMonitor(agent), ScMonitor(agent), CommonStateMonitor(agent),
            CommonHistoryMonitor(agent), IntegratedMonitor(agent), SramMonitor(agent)]
    if name == 'mbtb':
        return [MbtbCounterActivityMonitor(dut), MbtbEntryActivityMonitor(dut), MbtbEntryShadowMonitor(dut)]
    if name == 'ras':
        return [RasCommittedMonitor(RasAgent(dut))]
    if name == 'sc':
        return [ScThresholdMonitor(dut)]
    if name == 'tage':
        agent = TageAgent(dut)
        return [TagePredictionStateMonitor(dut, agent.ports.prediction, agent._decode),
            TageWriteActivityMonitor(dut), *(TageShadowMonitor(dut, table=table) for table in range(4))]
    if name == 'utage':
        agent = UtageAgent(dut)
        return [UtageUsefulMonitor(agent), *(UtageShadowMonitor(agent, table=table) for table in range(2))]
    return []


@pytest.mark.feature('ENV-IF-002')
@pytest.mark.parametrize('name', [pytest.param(name, marks=pytest.mark.dut(name))
    for name in ('abtb','bpu','ittage','mbtb','ras','sc','tage','ubtb','uras','utage')])
def test_native_dut_and_production_monitor_bindings(dut_factory, name):
    dut = dut_factory.create(name, coverage_name='memory-direct-bindings-smoke.dat')
    def forbidden(*args, **kwargs):
        raise AssertionError('production observations must not call legacy internal getters')
    dut.GetInternalSignal = dut.GetInternalSignalList = forbidden
    view = require_memory_direct(dut)
    assert view.base > 0 and view.names()
    assert not dut.clock.IsVPIBinded() and not dut.reset.IsVPIBinded()
    # These are infrastructure checks, not functional credit: no internal writes.
    monitors = observation_layers(name, dut)
    dut.Step(2)
    dut.reset.Set(0)
    dut.Step(4)
    for monitor in monitors:
        assert monitor.binding.bits.sample() is not None
    assert not dut.internal_signals
    assert all(not signal.IsVPIBinded() for signal in view._signals.values())
