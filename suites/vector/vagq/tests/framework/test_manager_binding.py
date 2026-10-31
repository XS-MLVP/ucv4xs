"""Native/protocol binding qualification, not allocation-function coverage."""
import pytest

from suites.vector.vagq.manager.driver import ManagerDriver
from suites.vector.vagq.manager.ports import Ports

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_native_bindings_and_initial_write_modes(manager_dut):
    dut = manager_dut
    ports = Ports.bind(dut)
    ManagerDriver(ports)  # The protocol, not the native resource, selects RiseWrite.
    assert int(dut.dut.GetXSignalCFGBasePtr()) > 0
    assert dut.clock.IsImmWrite()
    assert dut.reset.IsRiseWrite() and dut.reset.U() == 1
    for signal in ports.stimulus.values():
        assert signal.IsRiseWrite() and signal.U() == 0
    committed = ports.observed.control.reqCount
    assert not committed.IsVPIBinded() and committed.U() == 0
    dut.in_reqCount.Set(5)
    assert dut.in_reqCount.U() == 5 and committed.U() == 0
