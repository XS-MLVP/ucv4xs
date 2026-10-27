"""Check genuine recurrence, all full-tag widths, and actual physical-bank recipes."""
import pytest
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.phr.model import MASK
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.case.bypass.history_plan import recipe
from bpuverify.bpu.case.bypass.history_plan import recurring_history
from bpuverify.bpu.case.bypass.history_plan import read_indices
from bpuverify.bpu.case.bypass.history_plan import full_tags


@pytest.mark.parametrize('bank',(2,3))
def test_recurring_history_reaches_actual_index_bank(bank):
    plan=recipe(bank)
    assert plan['expected_lower_index']%4==bank
    assert plan['expected_conditional_upper_index']%4==bank
    assert plan['path_hashes'][0]!=0 and plan['path_hashes'][1]!=0
    assert (plan['path_hashes'][0]^plan['path_hashes'][1])&63==0


@pytest.mark.parametrize('bank',(2,3))
@pytest.mark.parametrize('phase',('conditional','fallback'))
def test_all52_history_bits_and_both_full_tags_representable(bank,phase):
    plan=recipe(bank)
    position=plan['position'] if phase=='conditional' else plan['fallback']
    history=0
    for _ in range(270):
        history=((history<<2)^path_hash((plan['pc']&~15)+position,plan['pc']))&MASK
        tags=full_tags(plan['pc'],folds(history))
        assert all(0<=tag<256 for tag in tags)
    assert history==plan[phase+'_history']


@pytest.mark.parametrize('bank',(2,3))
def test_upper_bank_cannot_be_inferred_from_pc_or_two_history_bits(bank):
    plan=recipe(bank)
    assert (plan['pc']&3)!=bank
    history=plan['conditional_history']
    assert read_indices(plan['pc'],(folds(history)[2],folds(history)[9]))[1]%4==bank


def test_invalid_bank_rejected():
    with pytest.raises(ValueError):
        recipe(0)
