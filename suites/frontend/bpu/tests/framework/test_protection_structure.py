"""Fail-closed source attribution controls, never DUT functional coverage."""
from pathlib import Path
import re
import pytest
from tools.review_protection_structure import SourceShapeError,review,uncomment


@pytest.mark.parametrize('dut',('utage','bpu'))
@pytest.mark.parametrize('name,initial,maintenance',(
    ('BypassShadowBuffer.sv',1,'decrement'),('BypassShadowBuffer_1.sv',2,'halve')))
def test_all_actual_protection_destinations_and_complete_read_paths_are_reviewed(dut,name,initial,maintenance):
    source=Path('rtl')/dut/name;r=review(source.read_text())
    assert r.initial==initial and r.maintenance==maintenance
    assert len(r.rows)==512 and [row['index'] for row in r.rows]==list(range(512))
    assert len(r.clauses)==2560
    assert {row['role'] for row in r.clauses.values()}=={
        'allocation-choice','allocation-initialize','saturation-choice','saturation-preserve','counter-change'}
    assert set(r.clauses)=={line for row in r.rows for line in row['lines'].values()}


@pytest.mark.parametrize('name',('BypassShadowBuffer.sv','BypassShadowBuffer_1.sv'))
def test_integrated_and_isolated_child_identity_requires_exact_bytes_not_equal_names(name):
    assert (Path('rtl/bpu')/name).read_bytes()==(Path('rtl/utage')/name).read_bytes()


@pytest.mark.parametrize('fault',(
    'packed-bank-order','packed-other-row','t0-bank-selector','t1-bank-selector',
    't0-row-selector','t1-row-selector','unqualified-learning','wrong-saturation-boundary',
    'wrong-increment','wrong-reset','conditional-reset','wrong-maintenance',
    'wrong-bank-decoder','wrong-row-decoder','wrong-last-bank','mixed-initial',
    'extra-write','extra-blocking-write','extra-learning-guard','missing-cell','wrong-destination'))
def test_unknown_or_corrupted_structure_cannot_be_called_a_uniform_replica(fault):
    text=uncomment(Path('rtl/utage/BypassShadowBuffer.sv').read_text())
    def change(before,after):
        nonlocal text
        assert before in text;text=text.replace(before,after,1)
    if fault=='packed-bank-order':change('{usefulEntries_3_0_value},','{usefulEntries_2_0_value},')
    elif fault=='packed-other-row':change('{usefulEntries_3_64_value},','{usefulEntries_3_63_value},')
    elif fault=='t0-bank-selector':change('_GEN_126[io_train_t0_trainIndex_bits[1:0]]','_GEN_126[io_train_t0_trainIndex_bits[2:1]]')
    elif fault=='t1-bank-selector':change('_GEN_126[t1_trainIndex[1:0]]','_GEN_126[t1_trainIndex[2:1]]')
    elif fault=='t0-row-selector':change('_GEN_127[io_train_t0_trainIndex_bits[8:2]]','_GEN_127[io_train_t0_trainIndex_bits[7:2]]')
    elif fault=='t1-row-selector':change('_GEN_146[t1_trainIndex[8:2]]','_GEN_146[t1_trainIndex[7:2]]')
    elif fault=='unqualified-learning':change('& io_train_t1_update_bits_usefulValid','| io_train_t1_update_bits_usefulValid')
    elif fault=='wrong-saturation-boundary':change("_GEN_147 == 2'h0","_GEN_147 == 2'h1")
    elif fault=='wrong-increment':change("_GEN_147 + 2'h1","_GEN_147 + 2'h2")
    elif fault=='wrong-reset':change("usefulEntries_0_0_value <= 2'h0;","usefulEntries_0_0_value <= 2'h1;")
    elif fault=='conditional-reset':change("usefulEntries_0_0_value <= 2'h0;","if (io_train_t1_update_valid) begin usefulEntries_0_0_value <= 2'h0; end")
    elif fault=='wrong-maintenance':change("usefulEntries_0_0_value - 2'h1","usefulEntries_0_0_value + 2'h1")
    elif fault=='wrong-bank-decoder':change("_GEN_149 = t1_trainIndex[1:0] == 2'h0;","_GEN_149 = t1_trainIndex[1:0] == 2'h1;")
    elif fault=='wrong-row-decoder':change("_GEN_276 = t1_trainIndex[8:2] == 7'h7E;","_GEN_276 = t1_trainIndex[8:2] == 7'h7D;")
    elif fault=='wrong-last-bank':change('_GEN_148 & (&(t1_trainIndex[1:0]))','_GEN_148 & (&(t1_trainIndex[0:0]))')
    elif fault=='mixed-initial':change("usefulEntries_0_0_value <= 2'h1;","usefulEntries_0_0_value <= 2'h2;")
    elif fault=='extra-write':change('if (io_usefulReset) begin',"usefulEntries_0_0_value <= 2'h1; if (io_usefulReset) begin")
    elif fault=='extra-blocking-write':change('if (io_usefulReset) begin',"usefulEntries_0_0_value = 2'h1; if (io_usefulReset) begin")
    elif fault=='extra-learning-guard':change('if (_GEN_148 & _GEN_149 & _GEN_150) begin',
        'if (io_train_t1_update_valid) begin end if (_GEN_148 & _GEN_149 & _GEN_150) begin')
    elif fault=='missing-cell':
        text,count=re.subn(r'\breg\s*\[1:0\]\s*usefulEntries_3_127_value\s*;','',text,count=1);assert count==1
    else:change('usefulEntries_0_0_value <= _GEN_147;','usefulEntries_0_1_value <= _GEN_147;')
    with pytest.raises(SourceShapeError):review(text)


def test_comments_cannot_supply_missing_read_or_write_definitions():
    text=Path('rtl/utage/BypassShadowBuffer.sv').read_text()
    text,count=re.subn(r'_GEN_147 = _GEN_146\[t1_trainIndex\[8:2\]\];',
        '/* _GEN_147 = _GEN_146[t1_trainIndex[8:2]]; */',text,count=1)
    assert count==1
    with pytest.raises(SourceShapeError):review(text)


def test_module_name_does_not_substitute_for_short_long_parameter_semantics():
    text=Path('rtl/utage/BypassShadowBuffer.sv').read_text()
    text=text.replace('module BypassShadowBuffer(','module AnotherName(',1)
    r=review(text);assert r.module=='AnotherName' and r.initial==1 and r.maintenance=='decrement'
