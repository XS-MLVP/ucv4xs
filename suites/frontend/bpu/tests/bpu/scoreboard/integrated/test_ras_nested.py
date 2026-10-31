"""Independent PC-unit and committed-storage boundary checks, without a DUT."""
import pytest
from suites.frontend.bpu.ras.model.model import CommittedStack
from suites.frontend.bpu.ras.model.model import advance
from suites.frontend.bpu.bpu.case.ras.retirement import return_address


@pytest.mark.parametrize('offset', range(8))
@pytest.mark.parametrize('position', (0, 7, 15))
def test_return_address_uses_pruned_pc_and_byte_alignment(offset, position):
    assert return_address(0x40000800 + offset, position) == 0x40000800 + position + 1


@pytest.mark.parametrize('pc,position', ((-1, 0), (1 << 50, 0), (0, -1), (0, 16), (True, 0), (0, True)))
def test_return_address_rejects_invalid_units(pc, position):
    with pytest.raises(ValueError):
        return_address(pc, position)


def test_ordered_nested_commit_retains_popped_cells():
    state = CommittedStack()
    first, second = return_address(0x40000800, 15), return_address(0x40000900, 15)
    for action, address in ((2, first), (2, second), (1, None), (1, None)):
        state = advance(state, action, address=address)
    assert state.head == 0
    assert state.native()['cells'][1:3] == [dict(address=first, counter=0), dict(address=second, counter=0)]
