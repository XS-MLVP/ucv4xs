"""SbufferData transaction and observation controls."""
import pytest

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('ports', [(0, 0), (2,), (1, 0)])
def test_data_transactions_reject_ambiguous_physical_port_priority(ports):
    from suites.memblock.sbuffer.testbenches.sbuffer_data.model import WriteRequest
    from suites.memblock.sbuffer.testbenches.sbuffer_data.transactions import Op
    req = WriteRequest(1, 1, 7, 0)
    with pytest.raises(ValueError, match='unique, increasing'):
        Op((req,) * len(ports), ports=ports).active()


def test_data_snapshot_does_not_retain_live_signal_references():
    from types import SimpleNamespace
    from suites.memblock.sbuffer.testbenches.sbuffer_data.env.ports import SbufferDataPorts
    ports = object.__new__(SbufferDataPorts)
    mask, data = SimpleNamespace(value=1), SimpleNamespace(value=0x55)
    ports.masks, ports.data = (((mask,),),), (((data,),),)
    before = ports.capture(None)
    mask.value, data.value = 0, 0xAA
    assert before.masks == ((1,),) and before.data == (((0x55,),),)
    assert ports.capture(None).masks == ((0,),)
