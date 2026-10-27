"""A cancelled neutral prediction cannot borrow an equal-encoding lifetime."""
from dataclasses import replace
import pytest
from bpuverify.ras.model.semantic import RasReference,Events,Recovery,Retirement


@pytest.mark.parametrize('operation',('retire','recover'))
def test_restoring_an_older_original_cancels_younger_neutral_lifetimes(operation):
    model=RasReference()
    old=model.capture_original();model.advance(Events(action=0,origin=old))
    young=model.capture_original();model.advance(Events(action=0,origin=young))
    assert old.program is young.program and model.original_is_live(young)
    model.advance(Events(recovery=Recovery(0,0,0,origin=old)));model.advance()
    assert model.original_is_live(old) and not model.original_is_live(young)
    state=model.state()
    bad=(Events(retirement=Retirement(0,0,0,young)) if operation=='retire'
        else Events(recovery=Recovery(0,0,0,origin=young)))
    with pytest.raises(ValueError,match='cancelled'):
        model.advance(bad)
    assert model.state()==state


@pytest.mark.parametrize('action',(-1,4,True,'call'))
def test_invalid_retirement_action_is_atomic_even_with_a_valid_same_boundary_call(action):
    model=RasReference()
    state=model.state()
    with pytest.raises(ValueError,match='retirement action'):
        model.advance(Events(action=2,address=0x200,retirement=Retirement(0,0,action)))
    assert model.state()==state


def test_forecast_preserves_the_exact_original_registry_and_all_live_state():
    model=RasReference()
    origin=model.capture_original()
    before=model.state()
    future=model.preview(Events(action=2,address=0x200,origin=origin))
    assert model.state()==before and not model.original_is_live(origin)
    assert future.original_is_live(origin) and future.program.head.address==0x200
    assert future.require_original(origin) is origin
