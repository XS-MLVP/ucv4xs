"""Retention is an optional read-only observation, not a driver protocol."""
from types import SimpleNamespace as NS
import pytest

from bpuverify.bpu.bundle import tage_service as module
from bpuverify.bpu.bundle.values import _plain


class Signal:
    def __init__(self,value=0):self.value=value


@pytest.mark.parametrize('retention',(False,True))
def test_service_bundle_uses_exact_memory_direct_fields_and_freezes_optional_retention(monkeypatch,retention):
    signals={}
    def signal(dut,name):return signals.setdefault(name,Signal())
    monkeypatch.setattr(module,'memory_signal_names',lambda dut:('TOP.unit.tage.io_enable',))
    monkeypatch.setattr(module,'memory_signal',signal)
    binding,ports=module.service_binding(NS(dut=NS(clock=object())),table=3,bank=0,include_retention=retention)
    sampler=binding.bits.compile_sampler()
    before=_plain(sampler())
    assert len(ports)==2 and len(before['writes'])==2
    assert ('dirty' in before)==('incoming' in before)==retention
    if retention:
        assert before['dirty']==((0,)*4,)*2
        assert tuple(before['incoming'][0]['bits'])==('row','valid','tag','counter')
        signals['unit.tage.tables_3.tage_entry_write_buffer_bank0.dirty_1_3'].value=1
        signals['unit.tage.tables_3.tage_entry_write_buffer_bank0.io_write_1_bits_entry_takenCtr_value'].value=6
        after=_plain(sampler())
        assert before['dirty'][1][3]==0 and after['dirty'][1][3]==1
        assert before['incoming'][1]['bits']['counter']==0 and after['incoming'][1]['bits']['counter']==6
    else:assert not any('.dirty_' in name or '.io_write_' in name for name in signals)


def test_useful_channel_is_read_only_and_keeps_enqueue_service_and_full_state_separate(monkeypatch):
    signals={}
    def signal(dut,name):return signals.setdefault(name,Signal())
    monkeypatch.setattr(module,'memory_signal_names',lambda dut:('TOP.unit.tage.io_enable',))
    monkeypatch.setattr(module,'memory_signal',signal)
    agent=NS(dut=NS(clock=object()))
    binding,ports=module.useful_service_binding(agent,table=3,bank=0)
    sampler=binding.bits.compile_sampler();before=_plain(sampler())
    assert len(ports)==len(before['incoming'])==len(before['queues'])==2
    assert tuple(before['writes'][0]['bits'])==('row','value')
    base='unit.tage.tables_3.tage_useful_write_buffer_bank0_way0.'
    signals[base+'io_enq_bits_usefulCtr_value'].value=1
    signals[base+'deq_ptr_value'].value=2
    after=_plain(sampler())
    assert before['incoming'][0]['bits']['value']==0 and after['incoming'][0]['bits']['value']==1
    assert before['queues'][0]['dequeue']==0 and after['queues'][0]['dequeue']==2
    assert after['writes'][0]['bits']['value']==0
    assert not any('entry_write_buffer' in name or '__Vdly' in name for name in signals)
    with pytest.raises(ValueError,match='not a useful service field'):
        module.useful_service_binding(agent,table=3,bank=0,include_retention=True)
