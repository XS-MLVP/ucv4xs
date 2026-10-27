"""Conservative source projection rejects unsupported or incomplete claims.

These tests need no DUT or solver installation. The explicit offline review
separately runs its UNSAT miter and SAT negative mutants with a named solver.
"""
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import pytest
from tools.protection_rule_review import extract,evaluate,miter,choose,bv

ROOT=Path(__file__).resolve().parents[2]
SOURCE=(ROOT/'rtl/utage/BypassShadowBuffer.sv').read_text()


@lru_cache(maxsize=1)
def projection():return extract(SOURCE)


def test_complete_projection_accounts_for_all_cells_and_current_read_leaves():
    p=projection()
    assert p.read_map==tuple(range(512))
    assert p.decoders==tuple((i%4,i//4) for i in range(512))
    assert p.allocation==(1,)*512 and p.reset==(0,)*512 and p.aging_step==(1,)*512
    assert p==extract((ROOT/'rtl/bpu/BypassShadowBuffer.sv').read_text())


MALFORMED=(
    ('missing-register','reg  [1:0]        usefulEntries_0_0_value;','reg  [2:0]        usefulEntries_0_0_value;'),
    ('wrong-control-width','input        io_train_t1_update_bits_usefulValid,','input  [1:0] io_train_t1_update_bits_usefulValid,'),
    ('wrong-qualification','io_train_t1_alloc_valid | io_train_t1_update_valid\n          & io_train_t1_update_bits_usefulValid;',
        'io_train_t1_alloc_valid & io_train_t1_update_valid\n          & io_train_t1_update_bits_usefulValid;'),
    ('wrong-saturation','(&_GEN_147) & io_train_t1_update_bits_needUseful','(&_GEN_147) | io_train_t1_update_bits_needUseful'),
    ('wrong-learning-step',"_GEN_147 + 2'h1", "_GEN_147 + 2'h2"),
    ('wrong-mux-age','_GEN_147 = _GEN_146[t1_trainIndex[8:2]]','_GEN_147 = _GEN_146[io_train_t0_trainIndex_bits[8:2]]'),
    ('wrong-update-target','usefulEntries_0_0_value <= _newUseful_T_13;','usefulEntries_0_1_value <= _newUseful_T_13;'),
    ('missing-hold-write','usefulEntries_0_0_value <= _GEN_147;','usefulEntries_0_0_value = _GEN_147;'),
    ('wrong-row-width',"t1_trainIndex[8:2] == 7'h0", "t1_trainIndex[8:2] == 2'h0"),
    ('wrong-aging-target',"usefulEntries_0_0_value == 2'h0 ? 2'h0 : usefulEntries_0_0_value - 2'h1", "usefulEntries_0_0_value == 2'h0 ? 2'h0 : usefulEntries_0_1_value - 2'h1"),
    ('nested-reset','if (reset) begin','if (io_writeSuccess) begin\n    if (reset) begin'),
    ('nested-aging','if (io_usefulReset) begin','if (io_writeSuccess) begin\n      if (io_usefulReset) begin'),
    ('extra-assignment','a1_chosenFirstMask <=','usefulEntries_0_0_value <= 2\'h2;\n      a1_chosenFirstMask <='),
    ('wide-selected-value','logic [1:0]        _GEN_147;','logic [2:0]        _GEN_147;'),
    ('extra-blocking-write','a1_chosenFirstMask <=','usefulEntries_0_0_value = 2\'h2;\n      a1_chosenFirstMask <='),
    ('guarded-reset',"usefulEntries_0_0_value <= 2'h0;", "if (io_writeSuccess) usefulEntries_0_0_value <= 2'h0;"),
    ('guarded-aging',"usefulEntries_0_0_value <=\n          usefulEntries_0_0_value ==", "if (io_writeSuccess) usefulEntries_0_0_value <=\n          usefulEntries_0_0_value =="),
    ('additional-active-writer','endmodule',"always @(*) begin usefulEntries_0_0_value = 2'h2; end\nendmodule"),
)


@pytest.mark.parametrize('name,before,after',MALFORMED,ids=[v[0] for v in MALFORMED])
def test_changed_or_unaccounted_logic_cannot_inherit_a_local_certificate(name,before,after):
    assert before in SOURCE,name
    mutated=SOURCE.replace(before,after,1)
    with pytest.raises(ValueError):extract(mutated)


def test_repeated_semantic_cases_include_reset_aging_allocation_saturation_and_other_owner_preservation():
    p=projection();state=[0]*512
    for value in range(4):
        state[0]=value;state[1]=3-value
        for reward in (False,True):
            assert evaluate(p,cell=0,index=0,state=state,update=True,valid=True,reward=reward)==(
                (1,2,3,3) if reward else (0,0,1,2))[value]
            assert evaluate(p,cell=0,index=0,state=state,update=True,valid=False,reward=reward)==value
            assert evaluate(p,cell=0,index=1,state=state,allocate=True,reward=reward)==value
        assert evaluate(p,cell=0,index=0,state=state,allocate=True)==1
        assert evaluate(p,cell=0,index=0,state=state,allocate=True,aging=True)==(0,0,1,2)[value]
        assert evaluate(p,cell=0,index=0,state=state,allocate=True,aging=True,reset=True)==0


@pytest.mark.parametrize('fault',('allocation','reset','aging','read-owner','write-owner'))
def test_supported_wrong_connections_survive_projection_and_have_concrete_semantic_counterexamples(fault):
    p=projection();state=[0]*512;state[0]=2;state[1]=0
    if fault=='allocation':
        before,after="usefulEntries_0_0_value <= 2'h1;","usefulEntries_0_0_value <= 2'h2;";flags=dict(allocate=True)
    elif fault=='reset':
        before,after="usefulEntries_0_0_value <= 2'h0;","usefulEntries_0_0_value <= 2'h1;";flags=dict(reset=True)
    elif fault=='aging':
        before="usefulEntries_0_0_value == 2'h0 ? 2'h0 : usefulEntries_0_0_value - 2'h1"
        after=before[:-1]+'2';flags=dict(aging=True)
    elif fault=='read-owner':
        before,after='{usefulEntries_0_0_value}','{usefulEntries_1_0_value}';flags=dict(update=True,valid=True,reward=True)
    else:
        before,after="_GEN_149 = t1_trainIndex[1:0] == 2'h0;","_GEN_149 = t1_trainIndex[1:0] == 2'h1;";flags=dict(allocate=True)
    assert before in SOURCE
    bad=extract(SOURCE.replace(before,after,1))
    assert evaluate(bad,cell=0,index=0,state=state,**flags)!=evaluate(p,cell=0,index=0,state=state,**flags)
    assert miter(bad)!=miter(p)


def test_miter_keeps_arbitrary_addresses_state_and_all_priority_inputs():
    text=miter(projection())
    for name in ('IDX','CELL'):assert f'(declare-fun {name} () (_ BitVec 9))' in text
    for name in ('RESET','AGE','ALLOC','UPDATE','VALID','REWARD'):assert f'(declare-fun {name} () Bool)' in text
    assert '(Array (_ BitVec 9) (_ BitVec 2))' in text
    assert '(assert (not (= ACTUAL EXPECTED)))' in text
    assert choose('IDX',tuple(range(512)),9,'IDX')=='IDX'
    assert choose('CELL',(1,)*512,2,bv(1,2))==bv(1,2)


def test_certificate_is_local_and_does_not_pretend_to_validate_direction_content_logic():
    # The first occurrence is the direction write qualifier, not _GEN_148.
    mutated=SOURCE.replace('io_train_t1_alloc_valid | io_train_t1_update_valid',
        'io_train_t1_alloc_valid & io_train_t1_update_valid',1)
    p=extract(mutated);original=projection()
    assert p.source_sha256!=original.source_sha256
    assert (p.read_map,p.decoders,p.allocation,p.reset,p.aging_step)==(
        original.read_map,original.decoders,original.allocation,original.reset,original.aging_step)
