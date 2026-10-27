"""The public endpoint profile must not even bind internal GHR/BW state."""
from types import SimpleNamespace as NS
import pytest
from bpuverify.bpu.bundle import common_history as module
from bpuverify.bpu.bundle.values import _plain


class Signal:
    def __init__(self,value=0):self.value=value


@pytest.mark.parametrize('observe_state',(False,True))
def test_public_only_binding_keeps_the_independent_model_free_of_actual_history_state(monkeypatch,observe_state):
    signals={}
    def signal(dut,name):return signals.setdefault(name,Signal())
    monkeypatch.setattr(module,'memory_signal_names',lambda dut:('TOP.unit.commonHR.commonHR_ghr',))
    monkeypatch.setattr(module,'memory_signal',signal)
    binding=module.common_history_binding(NS(dut=NS(clock=object())),observe_state=observe_state)
    sampler=binding.bits.compile_sampler();before=_plain(sampler())
    assert ('state' in before)==observe_state
    assert any('commonHR.commonHR_' in name for name in signals)==observe_state
    assert set(before['redirect']['meta'])=={'ghr','bw','hits','positions','kinds'}
    signals['unit.io_fromFtq_redirect_bits_meta_commonHRMeta_ghr'].value=0xA5
    assert before['redirect']['meta']['ghr']==0 and _plain(sampler())['redirect']['meta']['ghr']==0xA5
