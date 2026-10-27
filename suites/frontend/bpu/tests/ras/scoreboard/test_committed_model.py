"""Hand-derived retained-storage checks, not replay of RTL guard expressions."""
from dataclasses import replace
import pytest

from bpuverify.ras.model.model import Cell
from bpuverify.ras.model.model import CommittedStack
from bpuverify.ras.model.model import Group
from bpuverify.ras.model.model import advance


@pytest.mark.parametrize('count', range(1, 25))
def test_unique_calls_write_exactly_the_selected_slots(count):
    state, expected = CommittedStack(), [Cell()] * 8
    for index in range(1, count + 1):
        previous = state
        state = advance(state, 2, address=0x100 + index)
        expected[index % 8] = Cell(0x100 + index, 0)
        assert state.cells == tuple(expected) and state.head == index % 8
        assert previous.cells != state.cells and previous.evicted == state.evicted[:len(previous.evicted)]
    assert len(state.evicted) == max(0, count + 1 - 8)
    while len(state.groups) > 1:
        retained = state.cells
        state = advance(state, 1)
        assert state.cells == retained
    with pytest.raises(ValueError, match='bottom/empty'):
        advance(state, 1)


@pytest.mark.parametrize('slot', range(8))
@pytest.mark.parametrize('mode', ('normal', 'saturated'))
def test_repeat_count_rollover_keeps_neighbors_and_stale_cells(slot, mode):
    state, expected = CommittedStack(), [Cell()] * 8
    prefix = (slot - 1) % 8
    for index in range(1, prefix + 1):
        state = advance(state, 2, address=0x100 + index)
        expected[index % 8] = Cell(0x100 + index, 0)
    repetitions = 3 if mode == 'normal' else 9
    for count in range(repetitions):
        state = advance(state, 2, address=0x400)
        selected = slot if count < 8 else (slot + 1) % 8
        expected[selected] = Cell(0x400, count % 8)
        assert state.head == selected and state.cells == tuple(expected)
    for _ in range(repetitions):
        top = state.groups[-1]
        state = advance(state, 1)
        if top.counter:
            expected[top.slot] = Cell(top.address, top.counter - 1)
        assert state.cells == tuple(expected)
    assert state.projection()['top'] == (0x100 + prefix if prefix else 0)


def test_reset_sentinel_duplicate_and_detached_snapshots():
    state = CommittedStack()
    following = advance(state, 2, address=0)
    assert following.projection() == dict(top=0, ssp=0, sctr=1)
    assert following.cells == (Cell(0, 1),) + (Cell(),) * 7
    assert advance(following, 1) == state
    snapshot = following.native()
    snapshot['cells'][0]['counter'] = 7
    assert following.cells[0].counter == 1 and state.cells[0].counter == 0


@pytest.mark.parametrize('action,address', ((0, None), (3, None), (True, None),
    (2, None), (2, -1), (2, 1 << 50), (2, False), (1, 0)))
def test_reject_out_of_scope_requests_without_mutation(action, address):
    state = CommittedStack()
    with pytest.raises(ValueError):
        advance(state, action, address=address)
    assert state == CommittedStack()


@pytest.mark.parametrize('changed', (
    replace(CommittedStack(), cells=(Cell(),) * 7),
    replace(CommittedStack(), groups=()),
    replace(CommittedStack(), groups=(Group(0, 0, 0), Group(0, 0, 0))),
    replace(CommittedStack(), cells=(Cell(0, 8),) + (Cell(),) * 7),
    replace(CommittedStack(), cells=(Cell(1 << 50, 0),) + (Cell(),) * 7),
    replace(CommittedStack(), groups=(Group(1, 0, 0),)),
    replace(CommittedStack(), groups=(Group(0, 0, 8),)),
))
def test_reject_inconsistent_states(changed):
    with pytest.raises(ValueError):
        advance(changed, 2, address=0x100)
