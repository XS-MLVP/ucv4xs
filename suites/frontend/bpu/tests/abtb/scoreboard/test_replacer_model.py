import pytest
from suites.frontend.bpu.abtb.model.state.replacer import route
from suites.frontend.bpu.abtb.model.state.replacer import touch
from suites.frontend.bpu.abtb.model.state.replacer import update
from suites.frontend.bpu.abtb.model.state.replacer import victim


@pytest.mark.parametrize('way,expected', [(0, 5), (1, 4), (2, 2), (3, 0)])
def test_hand_calculated_touch_from_zero(way, expected):
    assert touch(0, way) == expected


@pytest.mark.parametrize('state,expected', [(0, 0), (1, 1), (2, 0), (3, 1),
                                           (4, 2), (5, 2), (6, 3), (7, 3)])
def test_hand_calculated_victims(state, expected):
    assert victim(state) == expected


def test_same_set_writer_is_not_sequentially_merged():
    states = [0] * 64
    port = dict(read_valid=1, read_set=7, read_mask=(0, 0, 1, 0),
                write_valid=1, write_set=7, write_way=0)
    actual = update(states, port)
    assert actual[7] == 5
    assert actual[7] != touch(touch(0, 2), 0)
    assert actual[:7] == [0] * 7 and actual[8:] == [0] * 56


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('set_index', range(64))
def test_full_public_encoded_address_grid(bank, set_index):
    assert route(0x40000800 + 2 * set_index, bank) == (bank, set_index)
