"""Check repeat boundaries independently before any real DUT execution."""
import pytest
from suites.frontend.bpu.ras.model.model import CommittedStack
from suites.frontend.bpu.ras.model.model import advance
from suites.frontend.bpu.bpu.case.ras.retirement import return_address
from suites.frontend.bpu.bpu.case.ras.repeat import CALL_PC
from suites.frontend.bpu.bpu.case.ras.repeat import POSITION
from suites.frontend.bpu.bpu.case.ras.repeat import expected_repeat_state


@pytest.mark.parametrize('offset', range(8))
@pytest.mark.parametrize('position', (0, 7, 15))
def test_return_address_units(offset, position):
    assert return_address(CALL_PC + offset, position) == CALL_PC + position + 1


@pytest.mark.parametrize('count', range(1, 14))
def test_full_retained_repeat_state_matches_closed_form(count):
    state = CommittedStack()
    for _ in range(count):
        state = advance(state, 2, address=return_address(CALL_PC, POSITION))
    assert state.native() == expected_repeat_state(count)
    assert len(state.groups) == (2 if count <= 8 else 3)
    assert state.evicted == ()


@pytest.mark.parametrize('count', (0, 14, -1, True))
def test_repeat_oracle_rejects_out_of_scope(count):
    with pytest.raises(ValueError):
        expected_repeat_state(count)
