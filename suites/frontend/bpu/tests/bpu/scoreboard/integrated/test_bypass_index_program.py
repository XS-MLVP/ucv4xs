"""Pure stimulus constraints; no DUT or raw coverage."""
import pytest
from suites.frontend.bpu.bpu.model.phr.model import MASK
from suites.frontend.bpu.bpu.model.phr.model import fold
from suites.frontend.bpu.bpu.model.phr.model import folds
from suites.frontend.bpu.bpu.model.phr.model import path_hash
from suites.frontend.bpu.bpu.case.bypass.two_program_plan import recipe
from suites.frontend.bpu.bpu.case.bypass.two_program_plan import full_tags
from suites.frontend.bpu.bpu.case.bypass.public_readback import public_readback_pair

@pytest.mark.parametrize("bank",(1,2,3))
def test_old_steady_upper_index_is_the_actual_missing_physical_bank(bank):
    plan=recipe(bank)
    old=plan["old"]
    assert old["expected_lower_index"]%4==old["expected_conditional_upper_index"]%4==bank

@pytest.mark.parametrize("bank",(1,2,3))
def test_two_programs_really_have_distinct_conditional_upper_indices(bank):
    plan=recipe(bank)
    assert plan["old"]["expected_conditional_upper_index"]!=plan["second"]["expected_conditional_upper_index"]

@pytest.mark.parametrize("bank",(1,2,3))
def test_both_cold_sources_are_genuinely_observable_in_aligned_stream(bank):
    pcs=sorted(program["pc"] for program in (recipe(bank)["old"],recipe(bank)["second"]))
    leads=[(pc-1)&~15 for pc in pcs]
    assert len(set(leads))==2 and leads[1]>leads[0]
    assert all((pc-2)&~15==lead for pc,lead in zip(pcs,leads,strict=True))

@pytest.mark.parametrize("bank",(1,2,3))
@pytest.mark.parametrize("key",("old","second"))
def test_every_conditional_and_fallback_transient_full_tag_fits_storage(bank,key):
    program=recipe(bank)[key]
    for position in (program["position"],program["fallback"]):
        history=0
        for _ in range(270):
            assert all(0<=tag<256 for tag in full_tags(program["pc"],folds(history)))
            history=((history<<2)^path_hash((program["pc"]&~15)+position,program["pc"]))&MASK
        expected=program["conditional_history"] if position==program["position"] else program["fallback_history"]
        assert history==expected

def test_invalid_bank_rejected():
    with pytest.raises(ValueError):
        recipe(0)


@pytest.mark.parametrize("bank",(1,2,3))
def test_second_program_steady_reads_can_commit_old_bank_and_do_not_alias_old_index(bank):
    from itertools import product
    from suites.frontend.bpu.bpu.case.bypass.two_program_plan import read_indices
    plan=recipe(bank)
    old,new=plan["old"],plan["second"]
    assert old["expected_conditional_upper_index"]%4!=new["expected_conditional_upper_index"]%4
    indices=set()
    for length in range(7):
        for sequence in product(new["path_hashes"],repeat=length):
            history=0
            for value in sequence:
                history=(history<<2)^value
            indices.add(read_indices(new["pc"],(fold(history,5,5),fold(history,9,9)))[1])
    assert old["expected_conditional_upper_index"] not in indices


from suites.frontend.bpu.bpu.model.bypass.index import IndexPipeline

def step(model,**updates):
    args=dict(reset=0,enable=1,fire0=1,fire2=1,s2=0,s3=0,pc=6,normal_folds=(31,31),tick=1)
    args.update(updates)
    model.advance(**args)

def test_index_pipeline_uses_nonblocking_old_a1_not_current_pc_or_phr_echo():
    model=IndexPipeline()
    step(model,tick=1,normal_folds=(31,25))
    assert model.a2 is None
    step(model,tick=3,normal_folds=(31,31))
    assert model.a2["indices"]==(25,31) and model.a2["source_tick"]==1
    step(model,tick=5)
    assert model.a2["indices"]==(25,25) and model.a2["source_tick"]==3

@pytest.mark.parametrize("control",("enable","fire0"))
def test_index_pipeline_holds_when_disabled_or_no_a0_fire(control):
    model=IndexPipeline()
    step(model)
    step(model,tick=3)
    before=model.a2.copy()
    step(model,tick=5,pc=70,**{control:0})
    assert model.a2==before

def test_s2_override_holds_a2_and_s3_override_has_priority():
    model=IndexPipeline()
    step(model)
    step(model,tick=3,pc=70)
    step(model,tick=5,pc=4)
    before,older=model.a2.copy(),model.a3.copy()
    step(model,tick=7,s2=1)
    assert model.a2==before
    model.a3=older
    step(model,tick=9,s2=1,s3=1)
    assert model.a2==older

def test_bpu_s2_fire_snapshots_old_a2_even_when_a2_changes():
    model=IndexPipeline()
    step(model)
    step(model,tick=3,pc=70)
    before=model.a2.copy()
    step(model,tick=5)
    assert model.a3==before and model.a2!=before

def test_reset_clears_a2_a3_but_does_not_cancel_unreset_a1_capture():
    model=IndexPipeline()
    step(model,reset=1,pc=70)
    assert model.a2["indices"]==model.a3["indices"]==(0,0)
    assert model.a1["indices"]==(89,89)
