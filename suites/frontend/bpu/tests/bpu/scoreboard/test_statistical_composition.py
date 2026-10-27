"""Pure comparator controls, never synthetic evidence of DUT behavior."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.statistical import composition_values


def fixture():
    token=object()
    read=NS(weights=((0,1,2,3,4,5,6,7),(4,5,6,7,8,9,10,11),
        (-1,-2,-3,-4,-5,-6,-7,-8),(31,-32,0,-1,1,2,3,4),
        (1,2,3,4,5,6,7,8),(-4,-3,-2,-1,0,1,2,3),
        (2,0,-2,4,6,8,10,12),tuple(range(-16,16))))
    branches=tuple(NS(position=position) for position in range(10))
    tagged={f'{slot}.{field}':value for slot,counter in enumerate((0,7,3,4,0,7,3,4,0,7))
        for field,value in (('counter',counter),('has_provider',1))}
    calls=[]
    def snapshot(received):
        if received is not token:raise ValueError('foreign original cannot borrow this read')
        return NS(read=read)
    def decision(received,*,enabled):
        assert received is token
        calls.append(enabled)
        return branches,tagged if enabled else {},None
    sources=NS(statistical_snapshot=snapshot,tage_decision=decision)
    # Fixed arithmetic vectors for the seven declared history rows and 32 biases.
    sums=(73,-51,15,31,45,57,69,81)
    totals=((42,44,46,48),(-74,-72,-70,-68),(0,2,4,6),(24,26,28,30),
        (46,48,50,52),(66,68,70,72),(86,88,90,92),(106,108,110,112))
    # Default position fold is low three bits XOR upper two bits; 8,9 select 1,0.
    actual=dict(history_sums=[v%1024 for v in sums],
        candidates=[[v%2048 for v in row] for row in totals],
        selected=[42,-72%2048,4,30,46,68,90,112,-74%2048,44])
    return sources,token,actual,calls


def test_exact_composition_checks_all_signed_candidates_and_original_branch_biases():
    sources,token,actual,calls=fixture()
    expected,observed=composition_values(sources,token,actual,tage_enabled=True)
    assert expected==observed and calls==[True]
    assert expected['history_sums']==(73,-51,15,31,45,57,69,81)
    assert len(expected['candidates'])==8 and sum(map(len,expected['candidates']))==32
    assert expected['selected']=={'0':42,'1':-72,'2':4,'3':30,'4':46,'5':68,'6':90,'7':112,'8':-74,'9':44}


@pytest.mark.parametrize('fault',('same-sign-sum','same-sign-total','wrong-bias','wrong-slot',
    'dropped-sign','narrow-overflow','missing-alternative','extra-alternative','candidate-owner-swap'))
def test_wrong_numeric_composition_fails_even_when_direction_and_authority_are_unchanged(fault):
    sources,token,actual,_=fixture()
    if fault=='same-sign-sum':actual['history_sums'][0]+=2
    elif fault=='same-sign-total':actual['candidates'][0][0]+=2
    elif fault=='wrong-bias':actual['selected'][0]=44
    elif fault=='wrong-slot':actual['selected'][1]=63
    elif fault=='dropped-sign':actual['history_sums'][1]=52
    elif fault=='narrow-overflow':actual['candidates'][1][0]=197
    elif fault=='missing-alternative':actual['candidates'][3].pop()
    elif fault=='extra-alternative':actual['candidates'][3].append(29)
    else:actual['candidates'][2],actual['candidates'][3]=actual['candidates'][3],actual['candidates'][2]
    expected,observed=composition_values(sources,token,actual,tage_enabled=True)
    with pytest.raises(AssertionError):Scoreboard('SC-signed-composition').check(expected=expected,actual=observed)


def test_disabled_tage_uses_independent_no_provider_bias_not_stale_hardware_counter():
    sources,token,actual,calls=fixture()
    actual['selected']=[42,-74%2048,0,24,46,66,86,106,-74%2048,42]
    expected,observed=composition_values(sources,token,actual,tage_enabled=False)
    assert expected==observed and calls==[False]


def test_absent_branch_payload_is_ignored_but_all_numeric_objects_still_compare():
    sources,token,actual,_=fixture()
    original=sources.tage_decision
    def decision(received,*,enabled):
        branches,tagged,late=original(received,enabled=enabled)
        return (branches[0],None,branches[2],None),tagged,late
    sources.tage_decision=decision
    actual['selected'][1]=actual['selected'][3]=1<<30
    expected,observed=composition_values(sources,token,actual,tage_enabled=True)
    assert expected==observed and set(expected['selected'])=={'0','2'}
    actual['candidates'][3][0]+=2
    assert composition_values(sources,token,actual,tage_enabled=True)[0]!=composition_values(sources,token,actual,tage_enabled=True)[1]


@pytest.mark.parametrize('weight,total',((-32,-504),(31,504)))
def test_signed_expansion_preserves_full_negative_and_positive_magnitudes(weight,total):
    sources,token,_,_=fixture()
    read=NS(weights=((weight,)*8,)*7+((weight,)*32,))
    sources.statistical_snapshot=lambda received:NS(read=read)
    partial=7*(2*weight+1)
    actual=dict(history_sums=[partial%1024]*8,candidates=[[total%2048]*4 for _ in range(8)],
        selected=[total%2048]*10)
    assert composition_values(sources,token,actual,tage_enabled=True)[0]==composition_values(sources,token,actual,tage_enabled=True)[1]


def test_foreign_original_cannot_borrow_equal_numeric_evidence():
    sources,_,actual,_=fixture()
    with pytest.raises(ValueError,match='foreign original'):
        composition_values(sources,object(),actual,tage_enabled=True)


def test_comparison_does_not_modify_sample_or_reference_weights():
    sources,token,actual,_=fixture()
    before=deepcopy(actual),deepcopy(sources.statistical_snapshot(token).read.weights)
    composition_values(sources,token,actual,tage_enabled=True)
    assert (actual,sources.statistical_snapshot(token).read.weights)==before


@pytest.mark.parametrize('slot',range(10))
def test_same_direction_and_threshold_category_cannot_hide_a_wrong_selected_magnitude(slot):
    sources,token,actual,_=fixture()
    def decoded(value):return value-2048 if value>=1024 else value
    old=decoded(actual['selected'][slot])
    newer=old+(2 if old>=0 else -2)
    assert (newer>=0,abs(newer)>10)==(old>=0,abs(old)>10)
    actual['selected'][slot]=newer%2048
    expected,observed=composition_values(sources,token,actual,tage_enabled=True)
    with pytest.raises(AssertionError,match='selected'):
        Scoreboard('SC-same-verdict-wrong-score').check(expected=expected,actual=observed)
