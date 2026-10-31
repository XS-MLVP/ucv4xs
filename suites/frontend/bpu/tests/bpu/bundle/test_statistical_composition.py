"""Static signed composition observations use the existing public Bundle."""
from toffee import Bundle
from suites.frontend.bpu.bpu.bundle.statistical import statistical_bundle
from suites.frontend.bpu.bpu.bundle.values import _plain


class Signal:
    def __init__(self):self.value=0


def test_composition_is_sampled_structurally_without_case_level_get_set():
    signals={}
    def signal(name):return signals.setdefault(name,Signal())
    bits=statistical_bundle(signal)
    assert isinstance(bits.prediction_composition,Bundle)
    sampler=bits.compile_sampler()
    before=_plain(sampler())['prediction_composition']
    names={f'sc.s2_sumPercsum_{w}' for w in range(4)}
    names|={f'sc.s2_totalPercsumAll_{w}_{b}' for w in range(4) for b in range(4)}
    names|={f'sc.s2_totalPercsum_{slot}' for slot in range(4)}
    assert names<=signals.keys() and len(names)==24
    signals['sc.s2_totalPercsumAll_3_2'].value=1023
    signals['sc.s2_totalPercsum_1'].value=999
    after=_plain(sampler())['prediction_composition']
    assert before['candidates'][3][2]==0 and after['candidates'][3][2]==1023
    assert before['selected'][1]==0 and after['selected'][1]==999
