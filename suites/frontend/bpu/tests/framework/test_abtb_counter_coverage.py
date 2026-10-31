"""Counter source-row attribution is independent of v_line arm counts."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.coverage import rtl as rtl_coverage
from suites.frontend.bpu.abtb.coverage.counter import source_index
from suites.frontend.bpu.abtb.coverage.counter import source_matrix


def block(bank=0,entry_set=0,way=0):
    name=f'takenCounter_{bank}_{entry_set}_{way}_value'
    return f"""reg [1:0] {name};
if (_needReset_T)
  {name} <= 2'h2;
else begin
  if (_needIncrease_T & ~t1_train_branch_taken) begin // /src/AheadBtb.scala:241
    if (|{name})
      {name} <= {name} - 2'h1;
  end
  else if (~(_needIncrease_T & ~t1_train_branch_taken)
           | (&{name})) begin // /src/SaturateCounter.scala:41
  end
  else
    {name} <= {name} + 2'h1;
end
"""


def fixture():
    text=''.join(block(b,s,w) for b in range(2) for s in range(2) for w in range(4))
    index=source_index(text.splitlines())
    lines=[line for line,owner in index['lines'].items()
        if owner['bank']==owner['set']==owner['way']==0 and owner['role'] in
        ('decrease_selection','decrement_nonzero_guard','decrement_assignment')]
    gaps=[dict(file='rtl/bpu/AheadBtb.sv',line=line,counter_gap=dict(index['lines'][line])) for line in lines]
    return text,index,gaps


def test_geometry_is_derived_from_declared_cells_not_hardcoded():
    _,index,gaps=fixture()
    assert len(index['cells'])==16
    matrix=source_matrix(gaps,index)
    assert matrix['unit']=='verilator_native_lcov_SF_DA_source_lines'
    assert matrix['mapped_source_lines']==matrix['uncovered_source_lines']==3
    assert matrix['unmapped_source_lines']==0 and matrix['cells_with_missing_lines']==1
    assert len(matrix['cells'])==16 and sum(row['missing_source_lines']==0 for row in matrix['cells'])==15
    assert matrix['source_line_hit_does_not_prove_counter_saturation_hold']


@pytest.mark.parametrize('before,after',[
    ("takenCounter_0_0_0_value <= 2'h2;","takenCounter_0_0_0_value <= 2'h1;"),
    ("takenCounter_0_0_0_value <= takenCounter_0_0_0_value - 2'h1;",
     "takenCounter_0_0_1_value <= takenCounter_0_0_1_value - 2'h1;"),
    ("takenCounter_0_0_0_value <= takenCounter_0_0_0_value + 2'h1;",
     "takenCounter_0_0_0_value <= takenCounter_0_0_0_value + 2'h2;"),
    ('if (|takenCounter_0_0_0_value)','if (takenCounter_0_0_0_value)'),
])
def test_malformed_declared_cell_fails_closed(before,after):
    text,_,_=fixture()
    assert before in text
    with pytest.raises(ValueError):source_index(text.replace(before,after,1).splitlines())


@pytest.mark.parametrize('fault',['duplicate_line','wrong_owner','unknown_cell'])
def test_native_source_key_and_cell_identity_are_checked(fault):
    _,index,gaps=fixture()
    gaps=deepcopy(gaps)
    if fault=='duplicate_line':gaps.append(deepcopy(gaps[0]))
    elif fault=='wrong_owner':gaps[0]['counter_gap']['way']^=1
    else:gaps[0]['counter_gap']['bank']=99
    with pytest.raises(ValueError):source_matrix(gaps,index)


def test_unsuffixed_first_selector_maps_before_first_counter_reference(tmp_path):
    path=tmp_path/'AheadBtb.sv'
    path.write_text(block(),encoding='utf-8')
    line=next(number for number,code in enumerate(block().splitlines(),1)
        if code.lstrip().startswith('if (_needIncrease_T'))
    assert rtl_coverage._abtb_counter_gap(path,line,['/src/AheadBtb.scala:241'],{})==dict(
        role='decrease_selection',bank=0,set=0,way=0)


@pytest.mark.parametrize('dut',['abtb','bpu'])
def test_native_DA_source_matrix_and_counter_arm_matrix_remain_separate(tmp_path,monkeypatch,dut):
    monkeypatch.setattr(rtl_coverage,'ROOT',tmp_path)
    source=tmp_path/'rtl'/dut/'AheadBtb.sv'
    source.parent.mkdir(parents=True)
    text,index,gaps=fixture()
    source.write_text(text,encoding='utf-8')
    merged=tmp_path/'merged.dat'
    merged.write_text(''.join(
        f"C '\x01f\x02{source}\x01l\x02{row['line']}\x01page\x02v_line/AheadBtb\x01S\x02{row['line']}' 0\n"
        for row in gaps),encoding='utf-8')
    summary=rtl_coverage._summarize(merged,dut)
    assert summary['source_lines']==dict(total=3,hit=0)
    assert summary['abtb_counter_source_matrix']['mapped_source_lines']==3
    assert summary['abtb_counter_matrix']['mapped_line_points']==1
    assert {row['counter_gap']['role'] for row in summary['uncovered_rtl_source_lines']}=={
        'decrease_selection','decrement_nonzero_guard','decrement_assignment'}
