"""Only real memory-direct fields are bound; no fabricated constant inputs."""
from types import SimpleNamespace as NS
import pytest
from suites.frontend.bpu.bpu.bundle import indirect_service as module
from suites.frontend.bpu.bpu.bundle.values import _plain


class Signal:
    def __init__(self,value=0):self.value=value


@pytest.mark.parametrize('table',(0,2))
@pytest.mark.parametrize('retention',(False,True))
def test_complete_target_bundle_keeps_actual_input_and_service_shapes_distinct(monkeypatch,table,retention):
    signals={}
    def signal(dut,name):
        assert 'io_write_0_bits_entry_valid' not in name and 'paddingBit' not in name
        return signals.setdefault(name,Signal())
    monkeypatch.setattr(module,'memory_signal_names',lambda dut:('TOP.unit.ittage.io_enable',))
    monkeypatch.setattr(module,'memory_signal',signal)
    binding,ports=module.indirect_service_binding(NS(dut=NS(clock=object())),table=table,bank=0,include_retention=retention)
    sampler=binding.bits.compile_sampler();before=_plain(sampler())
    assert len(ports)==1 and ('dirty' in before)==retention
    assert set(before['write']['bits'])=={'row','valid','tag','confidence','useful','offset','pointer','pc_region','mask'}
    assert set(before['incoming']['bits'])==set(before['write']['bits'])-{'valid'}
    base=f'unit.ittage.tables_{table}.ittage_write_buffer_bank0.'
    signals[base+'io_read_0_bits_entry_targetOffset_pointer'].value=3
    signals[base+'io_write_0_bits_entry_targetOffset_pointer'].value=2
    after=_plain(sampler())
    assert before['write']['bits']['pointer']==0 and after['write']['bits']['pointer']==3
    assert after['incoming']['bits']['pointer']==2
