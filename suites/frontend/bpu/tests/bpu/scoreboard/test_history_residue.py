"""Owned history invariants, not generated RTL/register emulation."""
from dataclasses import replace
import pytest

from bpuverify.bpu.model.path_history import PathHistoryReference,WIDTH,SHIFT
from bpuverify.bpu.coverage.history_gaps import residue_contract


def test_owned_cursor_orbit_is_closed_under_hold_taken_and_any_owned_restore():
    model=PathHistoryReference();saved=[]
    for count in range(2*WIDTH//SHIFT):
        saved.append(model.checkpoint())
        current=model.advance(taken=True,cfi_pc=0x40000804,target=0x40000A00)
        model.retire(current)
    reachable=set(residue_contract()['reachable_values'])
    assert {s.metadata()['phrPtr']['value'] for s in saved}==reachable
    assert {s.metadata()['phrPtr']['flag'] for s in saved}=={0,1}
    # Exhaustive model-state closure, not a DUT coordinate regression.
    for checkpoint in saved:
        for taken in (False,True):
            current=model.advance(taken=taken,cfi_pc=0x40000804,target=0x40000A00,restore=checkpoint)
            assert current.metadata()['phrPtr']['value'] in reachable
            if not taken:assert current.metadata()==checkpoint.metadata() and current.history==checkpoint.history
            model.retire(current)


@pytest.mark.parametrize('fault',('copied','foreign','old-epoch','retired'))
def test_no_arbitrary_checkpoint_can_enter_the_owned_history_residue_proof(fault):
    model=PathHistoryReference();source=model.checkpoint()
    if fault=='copied':source=replace(source,taken_edges=1)
    elif fault=='foreign':source=PathHistoryReference().checkpoint()
    elif fault=='old-epoch':model.reset()
    else:model.retire(source)
    before=model.history,model.taken_edges,dict(model.owned)
    with pytest.raises(ValueError,match='owned'):model.advance(taken=True,cfi_pc=0x40000804,target=0x40000A00,restore=source)
    assert (model.history,model.taken_edges,model.owned)==before


def test_constraint_is_configuration_dependent_and_does_not_imply_unrestricted_input_safety():
    assert residue_contract()['alignment']==2
    assert residue_contract(51,2)['alignment']==1
    assert residue_contract(52,1)['alignment']==1
    assert not residue_contract()['unrestricted_input_proof']


@pytest.mark.parametrize('width,shift',((True,2),(52,False),(0,2),(52,0),(52,52)))
def test_invalid_geometry_cannot_generate_a_spurious_reachability_proof(width,shift):
    with pytest.raises(ValueError):residue_contract(width,shift)
